"""Aviso da esteira: manda um e-mail quando entra coisa que precisa de acao.

  python avisar.py             # manda de verdade, se houver o que avisar
  python avisar.py --seco      # mostra o que mandaria, sem enviar e sem marcar
  python avisar.py --teste     # manda um e-mail de teste e sai

POR QUE ISSO EXISTE. O cron guarda em silencio, e o problema original nunca foi falta de
banco: foi ninguem avisar. A TalentHQ mandou convite, lembrete e "final reminder" e os tres
morreram na caixa. Esteira que so' armazena reproduz a mesma falha, so' que organizada.

O QUE DISPARA. So' o que tem prazo ou exige acao:
  - estado OFERTA ou EXPIRANDO
  - qualquer mensagem com acao detectada (assinar, prazo vencendo, convite de 0 connects,
    recrutador falou, gravar video, pediu material)
Resposta comum de "recebemos sua candidatura" NAO dispara nada. Aviso que toca demais vira
aviso que ninguem le.

UMA VEZ SO'. `vagas_emails.avisado_em` marca o que ja saiu. Sem isso o cron de 15 minutos
reenviaria o mesmo alerta pra sempre, que e' o caminho mais curto pra voce filtrar a
esteira pro lixo.

CONTA BREVO SEPARADA, NAO A DA 2B. Log do Brevo mostra destinatario e assunto, e a conta da
2B tem outras pessoas dentro. Alerta de busca de emprego nao passa por la'. As chaves saem
de `env.sh` (na VPS) ou do ambiente:
    BREVO_API_KEY_ESTEIRA   chave da conta nova
    BREVO_SENDER_ESTEIRA    remetente verificado nessa conta
    AVISO_PARA              destino (o e-mail dele)
"""
import sys, os, json, socket, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

API = "https://api.brevo.com/v3/smtp/email"


def _forcar_ipv4():
    """Sai sempre por IPv4.

    O Brevo autoriza por IP de origem, e a a VPS tem saida v4 (<IP-DE-SAIDA-DA-SUA-VPS>) E v6
    (<IPV6-DE-SAIDA-DA-SUA-VPS>). Sem forcar, a rota escolhe sozinha e o IP autorizado hoje
    pode nao ser o usado amanha: o alerta morreria com 401 parecendo chave errada.
    Um IP so' pra autorizar, e ele nao muda."""
    orig = socket.getaddrinfo

    def so_v4(host, port, family=0, *a, **kw):
        return orig(host, port, socket.AF_INET, *a, **kw)

    socket.getaddrinfo = so_v4


_forcar_ipv4()

CHAVE = os.environ.get("BREVO_API_KEY_ESTEIRA", "")
DE = os.environ.get("BREVO_SENDER_ESTEIRA", "")
PARA = os.environ.get("AVISO_PARA", "")

# Assunto por estado, do mais urgente pro menos.
PESO = {"OFERTA": 0, "EXPIRANDO": 1, "convite": 2, "entrevista": 3}


def pendentes(cur):
    cur.execute("""
        select id, data, remetente, assunto, estado, acoes
        from vagas_emails
        where ruido is null and avisado_em is null
          and (estado in ('OFERTA','EXPIRANDO') or acoes <> '{}')
        order by array_position(array['OFERTA','EXPIRANDO','convite','entrevista'],
                                estado) nulls last, data desc
    """)
    return cur.fetchall()


def montar(linhas):
    """Assunto e corpo. O assunto ja' diz o que e', porque e' o que aparece no push
    do celular e muitas vezes e' a unica coisa lida."""
    estados = [l[4] for l in linhas]
    if "OFERTA" in estados:
        cabeca = "OFERTA na caixa"
    elif "EXPIRANDO" in estados:
        cabeca = "prazo vencendo"
    else:
        cabeca = "%d item(ns) esperando" % len(linhas)
    assunto = "esteira: %s" % cabeca

    partes = ["<p style='font:15px/1.6 -apple-system,Segoe UI,Arial,sans-serif'>"
              "%d mensagem(ns) precisam de voce.</p>" % len(linhas)]
    partes.append("<table cellpadding='6' style='border-collapse:collapse;"
                  "font:14px/1.5 -apple-system,Segoe UI,Arial,sans-serif'>")
    for _id, data, rem, ass, est, ac in linhas:
        quando = data.strftime("%d/%m %H:%M") if data else ""
        rotulo = est or "-"
        acoes = ", ".join(ac) if ac else ""
        partes.append(
            "<tr style='border-top:1px solid #ddd'>"
            "<td style='white-space:nowrap'><b>%s</b></td>"
            "<td style='white-space:nowrap;color:#666'>%s</td>"
            "<td>%s<br><span style='color:#666'>%s</span>"
            "%s</td></tr>"
            % (rotulo, quando, (ass or "")[:90],
               (rem or "")[:60],
               ("<br><span style='color:#b00'>%s</span>" % acoes) if acoes else ""))
    partes.append("</table>")
    partes.append("<p style='font:13px -apple-system,Segoe UI,Arial,sans-serif;color:#666'>"
                  "Detalhe: <code>python esteira.py ler</code></p>")
    return assunto, "".join(partes)


def enviar(assunto, html):
    if not PARA:
        raise SystemExit("ERRO: AVISO_PARA nao esta definido. Sem destinatario o Brevo\n                         devolve 400, que nao parece falta de configuracao.")
    if not CHAVE or not DE:
        raise SystemExit(
            "faltam as chaves da conta Brevo da esteira:\n"
            "  BREVO_API_KEY_ESTEIRA  = %s\n"
            "  BREVO_SENDER_ESTEIRA   = %s\n"
            "Use a conta NOVA, nao a da 2B: o log do Brevo mostra destinatario e assunto."
            % ("ok" if CHAVE else "FALTA", DE or "FALTA"))
    corpo = json.dumps({
        "sender": {"email": DE, "name": "esteira-vagas"},
        "to": [{"email": PARA}],
        "subject": assunto,
        "htmlContent": html,
    }).encode("utf-8")
    req = urllib.request.Request(API, data=corpo, method="POST", headers={
        "api-key": CHAVE, "content-type": "application/json", "accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        det = e.read().decode("utf-8", "replace")[:300]
        if e.code == 401:
            # Gotcha conhecido: 401 do Brevo quase sempre e' IP nao autorizado, e a
            # mensagem parece chave errada. O proprio corpo diz qual IP ele viu.
            raise SystemExit(
                "Brevo devolveu 401 - quase sempre e' IP NAO AUTORIZADO, nao chave errada.\n"
                "Libere o IP de saida da a VPS (<IP-DE-SAIDA-DA-SUA-VPS>) em:\n"
                "  https://app.brevo.com/security/authorised_ips\n"
                "Detalhe do Brevo: %s" % det)
        raise SystemExit("Brevo %s: %s" % (e.code, det))


def main():
    seco = "--seco" in sys.argv
    if "--teste" in sys.argv:
        r = enviar("esteira: teste", "<p>Se voce esta lendo isto, o aviso funciona.</p>")
        print("enviado:", r)
        return

    c = db.conectar(); c.autocommit = False
    cur = c.cursor()
    linhas = pendentes(cur)
    if not linhas:
        print("nada novo pra avisar")
        c.close()
        return

    assunto, html = montar(linhas)
    print("%d item(ns) · assunto: %s" % (len(linhas), assunto))
    for _id, data, rem, ass, est, ac in linhas:
        print("  [%-9s] %-28s %s %s" % (est or "-", (rem or "")[:28], (ass or "")[:44],
                                        ("-> " + ", ".join(ac)) if ac else ""))
    if seco:
        print("\n--seco: nao enviei e nao marquei nada")
        c.close()
        return

    # Sem chave ainda: sai limpo. No cron de 15 minutos, erro repetido vira ruido de log
    # e some do radar; aviso calmo fica esperando a chave sem sujar nada. Nada e' marcado,
    # entao no dia em que a chave entrar estes itens saem no primeiro aviso.
    if not CHAVE or not DE:
        print("sem BREVO_API_KEY_ESTEIRA/BREVO_SENDER_ESTEIRA: %d item(ns) ficam na fila"
              % len(linhas))
        c.close()
        return

    r = enviar(assunto, html)
    # So' marca DEPOIS que o envio deu certo: se o Brevo falhar, o proximo cron tenta de novo
    cur.execute("update vagas_emails set avisado_em = now() where id = any(%s)",
                ([l[0] for l in linhas],))
    c.commit()
    print("enviado (%s) e %d marcadas" % (r.get("messageId", "ok"), cur.rowcount))
    c.close()


if __name__ == "__main__":
    main()
