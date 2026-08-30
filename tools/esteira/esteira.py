"""Esteira de vagas: armazena primeiro, classifica depois, le em batch.

  python esteira.py sync              # busca o que mudou e grava (e' o que o cron roda)
  python esteira.py sync --tudo       # ignora o historyId e revarre a janela inteira
  python esteira.py classificar       # reclassifica o que ficou atras da versao atual
  python esteira.py classificar --tudo
  python esteira.py ler               # fila: o que precisa de voce, ainda nao visto
  python esteira.py ler --todos       # inclui o que ja foi visto
  python esteira.py visto <id|all>    # marca como visto
  python esteira.py estado            # saude do sync

DESENHO. Tres passos que antes eram um:

  1. `sync`        Gmail -> Postgres. Idempotente, incremental, nunca rele' o que ja tem.
  2. `classificar` Postgres -> Postgres. Funcao pura sobre assunto+corpo. Melhorar regra
                   nao custa API nenhuma: bumpa VERSAO_REGRA e roda de novo.
  3. `ler`         a fila humana.

POR QUE ISSO IMPORTA. Na versao anterior buscar e classificar eram a mesma passada, entao
regra nova exigia baixar tudo outra vez e o que passou batido ficava perdido. Foi assim que
uma carta proposta assinada e um convite de entrevista em video ficaram 6 dias invisiveis.

POR QUE CRON E NAO WEBHOOK. Push do Gmail exige Cloud Pub/Sub, endpoint HTTPS publico e
`users().watch()` renovado a cada 7 dias, senao para em silencio. Para UMA caixa sao tres
pecas novas. `historyId` da' o delta desde a ultima vez, entao um cron curto custa quase
nada e tem uma peca so'.

AVISO QUE MATA CRON: app OAuth em publishing status "Testing" tem refresh token que expira
em **7 dias**. Para o cron sobreviver o app precisa estar "In production". Uso proprio nao
exige verificacao; so' mantem o aviso de app nao verificado no consentimento.

CORPO: guardado so' de quem NAO esta na lista de ruido. De remetente cortado guarda apenas
remetente, assunto e data, o suficiente pra auditar o corte sem armazenar newsletter e
e-mail pessoal.
"""
import sys, os, re
from datetime import timezone
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db
import gmail_vagas as G

# Bumpar isto faz `classificar` reprocessar tudo. E' o botao de "melhorei a regra".
VERSAO_REGRA = 3

JANELA_PADRAO = 45   # dias, usado no primeiro sync e quando o historyId morre


# ---------------------------------------------------------------- helpers ----------

def servico():
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=G.creds(), cache_discovery=False)


def email_de(s):
    m = re.search(r"[\w.+-]+@[\w.-]+", s or "")
    return (m.group(0) if m else (s or "")).lower()


def quando(s):
    try:
        d = parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def motivo_ruido(remetente_email, assunto):
    if remetente_email in G.RUIDO_DE:
        return "remetente na lista de ruido"
    a = G.sem_acento(assunto)
    for p in G.RUIDO_ASSUNTO:
        if p in a:
            return "assunto: %s" % p
    return None


def linha(svc, mid):
    """Baixa uma mensagem e devolve a tupla pronta pro upsert."""
    msg = svc.users().messages().get(userId="me", id=mid, format="full").execute()
    cab = {h["name"].lower(): h["value"]
           for h in msg.get("payload", {}).get("headers", [])}
    assunto = cab.get("subject", "") or ""
    remetente = cab.get("from", "") or ""
    rem = email_de(remetente)
    ruido = motivo_ruido(rem, assunto)
    eu = any(e in remetente.lower() for e in G.EU)
    corpo = None if ruido else G.texto(msg)
    return (mid, msg.get("threadId"), quando(cab.get("date", "")), remetente, rem,
            assunto, corpo, eu, ruido)


UPSERT = """
insert into vagas_emails
  (id, thread_id, data, remetente, remetente_email, assunto, corpo, eu_mandei, ruido)
values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
on conflict (id) do update set
  -- só reescreve o que pode ter mudado de leitura; nunca mexe em visto/nota.
  ruido = excluded.ruido,
  corpo = coalesce(excluded.corpo, vagas_emails.corpo)
returning (xmax = 0) as inserido
"""


# ------------------------------------------------------------------- sync ----------

def sync(tudo=False):
    svc = servico()
    c = db.conectar(); c.autocommit = False
    cur = c.cursor()
    cur.execute("select history_id from vagas_sync where id=1")
    (hid,) = cur.fetchone()

    ids, modo = [], ""
    if hid and not tudo:
        # Caminho incremental: so' o que mudou.
        try:
            pg = None
            while True:
                r = svc.users().history().list(userId="me", startHistoryId=hid,
                                               historyTypes=["messageAdded"],
                                               pageToken=pg).execute()
                for h in r.get("history", []) or []:
                    for a in h.get("messagesAdded", []) or []:
                        ids.append(a["message"]["id"])
                pg = r.get("nextPageToken")
                if not pg:
                    break
            modo = "incremental desde historyId %s" % hid
        except Exception as e:
            if "404" in str(e) or "failedPrecondition" in str(e):
                # historyId do Gmail caduca depois de ~1 semana. Cai pra janela.
                modo = "historyId caducou, caiu pra janela de %dd" % JANELA_PADRAO
                hid = None
            else:
                cur.execute("update vagas_sync set ultimo_erro=%s, ultimo_sync=now() "
                            "where id=1", (str(e)[:400],))
                c.commit(); c.close()
                raise

    if not hid or tudo:
        q = "(%s OR %s) newer_than:%dd" % (
            " OR ".join(G.FRASES),
            " OR ".join("from:%s" % d for d in sorted(set(G.ATS) | G.dominios_do_quadro())),
            JANELA_PADRAO)
        pg = None
        while True:
            r = svc.users().messages().list(userId="me", q=q, maxResults=500,
                                            pageToken=pg).execute()
            ids += [m["id"] for m in (r.get("messages", []) or [])]
            pg = r.get("nextPageToken")
            if not pg:
                break
        modo = modo or ("janela de %dd (primeiro sync)" % JANELA_PADRAO)

    ids = list(dict.fromkeys(ids))
    # Nao rele' o que ja esta gravado: e' o ponto todo de ter banco.
    if ids:
        cur.execute("select id from vagas_emails where id = any(%s)", (ids,))
        ja = {r[0] for r in cur.fetchall()}
        novos = [i for i in ids if i not in ja]
    else:
        novos = []
    print("modo: %s" % modo)
    print("ids vistos: %d · ja no banco: %d · baixando: %d"
          % (len(ids), len(ids) - len(novos), len(novos)))

    inseridos = 0
    for i, mid in enumerate(novos, 1):
        try:
            cur.execute(UPSERT, linha(svc, mid))
            if cur.fetchone()[0]:
                inseridos += 1
        except Exception as e:
            print("  falhou %s: %s" % (mid, str(e)[:90]))
            c.rollback()
            continue
        if i % 25 == 0:
            c.commit()
            print("  ... %d/%d" % (i, len(novos)))
    c.commit()

    # Guarda o ponteiro DEPOIS de gravar, senao um erro no meio perde mensagem.
    perfil = svc.users().getProfile(userId="me").execute()
    cur.execute("""update vagas_sync set history_id=%s, ultimo_sync=now(), ultimo_erro=null,
                   mensagens=(select count(*) from vagas_emails) where id=1""",
                (str(perfil.get("historyId")),))
    c.commit()
    print("gravados: %d · historyId agora: %s" % (inseridos, perfil.get("historyId")))
    c.close()
    return inseridos


# ------------------------------------------------------------ classificar ----------

def classificar(tudo=False):
    c = db.conectar(); c.autocommit = False
    cur = c.cursor()
    if tudo:
        cur.execute("select id, assunto, corpo, eu_mandei, ruido from vagas_emails")
    else:
        cur.execute("""select id, assunto, corpo, eu_mandei, ruido from vagas_emails
                       where versao_regra is null or versao_regra < %s""", (VERSAO_REGRA,))
    alvo = cur.fetchall()
    print("classificando %d mensagem(ns) na versao %d" % (len(alvo), VERSAO_REGRA))

    mudou = 0
    for mid, assunto, corpo, eu, ruido in alvo:
        if ruido:
            est, ac = None, []
        elif eu:
            est, ac = "EU RESPONDI", []
        else:
            est, ac = G.classificar((assunto or "") + "\n" + (corpo or ""))
        cur.execute("""update vagas_emails set estado=%s, acoes=%s, versao_regra=%s,
                       classificado_em=now() where id=%s
                       and (estado is distinct from %s or acoes is distinct from %s
                            or versao_regra is distinct from %s)""",
                    (est, ac, VERSAO_REGRA, mid, est, ac, VERSAO_REGRA))
        mudou += cur.rowcount
    c.commit()

    cur.execute("""select coalesce(estado,'sem rotulo') e, count(*) from vagas_emails
                   where ruido is null group by 1 order by 2 desc""")
    print("\nestado atual do banco (fora do ruido):")
    for e, n in cur.fetchall():
        print("  %-14s %4d" % (e, n))
    cur.execute("select count(*) from vagas_emails where ruido is not null")
    print("  %-14s %4d" % ("(ruido)", cur.fetchone()[0]))
    print("\nlinhas alteradas: %d" % mudou)
    c.close()


# -------------------------------------------------------------------- ler ----------

PRIORIDADE = ["OFERTA", "EXPIRANDO", "convite", "entrevista", "respondida",
              "rejeitada", "EU RESPONDI"]


def ler(todos=False):
    c = db.conectar()
    cur = c.cursor()
    # `todos` entra como parametro, nao como concatenacao: uma condicao sempre presente
    # que ou libera tudo ou filtra o nao-visto. Evita montar SQL com %.
    cur.execute("""select id, data, remetente, assunto, estado, acoes, visto
                   from vagas_emails
                   where ruido is null and (%s or not visto)
                   order by array_position(%s::text[], estado) nulls last, data desc""",
                (todos, PRIORIDADE))
    rs = cur.fetchall()

    fila = [r for r in rs if r[4] in ("OFERTA", "EXPIRANDO") or r[5]]
    if fila:
        print("!" * 92)
        print("PRECISA DE VOCE - %d" % len(fila))
        print("!" * 92)
        for mid, data, rem, ass, est, ac, v in fila:
            print("  %-10s %-11s %-28s %s" % (est or "-",
                                              data.strftime("%d/%m %H:%M") if data else "",
                                              rem[:28], (ass or "")[:42]))
            if ac:
                print("  %-10s %-11s %-28s -> %s" % ("", "", "", ", ".join(ac)))
            print("  %-10s id: %s" % ("", mid))

    for grupo in PRIORIDADE + [None]:
        g = [r for r in rs if r[4] == grupo]
        if not g:
            continue
        print("\n=== %s (%d) ===" % (grupo or "sem rotulo", len(g)))
        for mid, data, rem, ass, est, ac, v in g:
            print("  %s %-11s %-30s %s" % ("  " if v else "* ",
                                           data.strftime("%d/%m %H:%M") if data else "",
                                           rem[:30], (ass or "")[:44]))
    print("\n(* = ainda nao visto)")
    c.close()


def marcar_visto(alvo):
    c = db.conectar(); c.autocommit = True
    cur = c.cursor()
    if alvo == "all":
        cur.execute("update vagas_emails set visto=true, visto_em=now() "
                    "where not visto and ruido is null")
    else:
        cur.execute("update vagas_emails set visto=true, visto_em=now() where id=%s",
                    (alvo,))
    print("marcadas %d" % cur.rowcount)
    c.close()


def estado():
    c = db.conectar()
    cur = c.cursor()
    cur.execute("select history_id, ultimo_sync, ultimo_erro, mensagens from vagas_sync")
    h, u, e, n = cur.fetchone()
    print("historyId ..: %s" % h)
    print("ultimo sync : %s" % u)
    print("mensagens ..: %s" % n)
    print("ultimo erro : %s" % (e or "nenhum"))
    cur.execute("""select count(*) filter (where ruido is null),
                          count(*) filter (where ruido is not null),
                          count(*) filter (where ruido is null and not visto),
                          count(*) filter (where versao_regra < %s
                                           or versao_regra is null)
                   from vagas_emails""", (VERSAO_REGRA,))
    sinal, ruido, novo, atrasado = cur.fetchone()
    print("sinal ......: %d  (ruido guardado: %d)" % (sinal, ruido))
    print("nao vistos .: %d" % novo)
    print("a reclassif.: %d  (versao atual %d)" % (atrasado, VERSAO_REGRA))
    c.close()


if __name__ == "__main__":
    acao = sys.argv[1] if len(sys.argv) > 1 else "ler"
    flags = sys.argv[2:]
    if acao == "sync":
        sync(tudo="--tudo" in flags)
    elif acao == "classificar":
        classificar(tudo="--tudo" in flags)
    elif acao == "ler":
        ler(todos="--todos" in flags)
    elif acao == "visto":
        marcar_visto(flags[0] if flags else "all")
    elif acao == "estado":
        estado()
    elif acao == "cron":
        # o que o agendador chama: sync + classificar, quieto
        n = sync()
        classificar()
        print("cron ok, %d nova(s)" % n)
    else:
        raise SystemExit(__doc__)
