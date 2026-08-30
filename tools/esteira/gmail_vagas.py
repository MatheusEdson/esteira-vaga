"""Le a caixa e diz o que precisa de acao. SO' LEITURA.

  python gmail_vagas.py autorizar    # uma vez: consentimento no navegador
  python gmail_vagas.py varrer       # padrao 21 dias
  python gmail_vagas.py varrer 45    # janela maior
  python gmail_vagas.py tudo 7       # varredura TOTAL da janela, mostra o padrao da caixa

POR QUE OAUTH DE APP DESKTOP E NAO SERVICE ACCOUNT. Delegacao de dominio existe so' em
Workspace; `@gmail.com` e' conta de consumidor, entao nao ha dominio pra delegar. Nao
adianta compartilhar como se faz com property do Search Console. O caminho e' consentimento
do proprio usuario, gravado num refresh token local.

ESCOPO: `gmail.readonly`. Nao envia, nao responde, nao arquiva, nao apaga.

FILTRO: por CONTEUDO, nao por remetente. Medido em 27/08/2026:
  - caixa inteira, 45 dias ......... 2100 mensagens
  - filtro por remetente ...........   67
  - busca por conteudo .............  212, das quais 193 INVISIVEIS pro filtro anterior
Entre as invisiveis: convite de entrevista em video da TalentHQ com aviso de encerramento,
"final reminder" de uma vaga de Paid Media, uma carta proposta assinada, e o
Greenhouse inteiro, porque a lista dizia `greenhouse.io` e o Greenhouse manda de
`greenhouse-mail.io`.

POR QUE LISTA DE BLOQUEADOS E NAO DE PERMITIDOS. Allowlist de ATS **falha invisivel**: o
ATS que falta na lista simplesmente nao existe e ninguem descobre. Blocklist **falha
visivel**: o ruido que falta aparece na tela e a gente corta. Perder uma entrevista custa
mais que ler um assunto de newsletter.

NAO varre a caixa inteira no modo `varrer`: 426 mensagens em 7 dias (37% so' de ClickUp) e
a busca de texto do Gmail resolve no servidor por uma fracao do custo. O modo `tudo` existe
pra reauditar o padrao quando ele mudar.
"""
import sys, os, io, json, re, base64, unicodedata


def sem_acento(s):
    """Normaliza pra comparar. Existe porque a lista dizia "esta contratando" e o assunto
    real e' "esta' contratando" com acento: 12 alertas do LinkedIn vazaram por causa disso.
    Comparar sem acento mata a classe inteira de erro em vez de uma grafia por vez."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()

def _saida_utf8():
    """Reembala stdout so' quando roda como script.

    Fazer isso no import quebra quem importa o modulo: o pytest captura stdout e encontra
    um arquivo fechado, e o teste morre antes de rodar. Modulo nao mexe em stdout de quem
    o importa."""
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(line_buffering=True)

AQUI = os.path.dirname(os.path.abspath(__file__))
CRED = os.environ.get("GMAIL_CLIENT_SECRET",
                      os.path.join(AQUI, "gmail-oauth-client.json"))
TOKEN = os.path.join(AQUI, "_tmp", "gmail-token.json")
ESCOPO = ["https://www.googleapis.com/auth/gmail.readonly"]

# Ele. Mensagem partindo daqui e' prova de que ELE respondeu: marca, nao esconde.
EU = [e.strip() for e in os.environ.get("MEUS_EMAILS", "").split(",") if e.strip()]

# Plataformas e ATS. Rede extra pra mensagem SEM palavra no corpo (digest de DM do
# LinkedIn, convite da Upwork). Todos os de baixo foram MEDIDOS na caixa dele.
ATS = [
    "upwork.com", "t.upwork.com", "linkedin.com", "indeed.com", "deel.com",
    "ashbyhq.com", "greenhouse.io", "greenhouse-mail.io", "us.greenhouse-mail.io",
    "eu.greenhouse-mail.io", "workable.com", "lever.co", "gupy.io", "inhire.app",
    "ses-mail.inhire.app", "teamtailor.com", "teamtailor-mail.com", "hireflix.com",
    "thetalenthq.co", "candidates.thetalenthq.co", "manatal.com", "mail.manatal.com",
    "recrutei-mail.com.br", "torre.ai", "docusign.net", "bionictalent.com",
    "hireoverseas.com", "candidates.hireoverseas.com", "floowi.com", "virtustant.com",
    "geekhunter.com.br", "remotetalent", "activatetalent", "scalearmy", "hirewithnear",
    "jobs.hirewithnear.com", "ciadetalentos.com",
]

# Palavras de conteudo. Aspas = frase exata, resolvida no servidor do Gmail.
# PT e EN juntos: rejeicao em portugues nao casa com regex em ingles (custou a Skyone).
FRASES = [
    '"your application"', '"sua candidatura"', '"sua inscricao"', '"sua inscricao"',
    '"we received your"', '"recebemos sua"', '"thank you for applying"',
    '"obrigado por se candidatar"', '"processo seletivo"', '"moving forward"',
    '"other candidates"', '"outros candidatos"', '"outros perfis"',
    '"next steps"', '"proximos passos"',
    '"offer letter"', '"job offer"', '"proposta de trabalho"', '"carta proposta"',
    '"interview"', '"entrevista"', '"talent acquisition"', '"recrutador"',
    '"hiring team"', '"hiring manager"', '"schedule a call"', '"agendar uma conversa"',
    '"take-home"', '"assessment"', '"teste tecnico"',
    '"final reminder"', '"aquisicao de talentos"',
]

# Ruido MEDIDO. Cada linha tem a contagem de quando entrou, pra ninguem tirar no escuro.
RUIDO_DE = [
    # --- alerta de vaga e social (365 de 436 na janela de 45d) ---
    "jobalerts-noreply@linkedin.com",       # 257 alerta de vaga
    "donotreply@match.indeed.com",          # 44 alerta
    "newsletters-noreply@linkedin.com",     # 27
    "messages-noreply@linkedin.com",        # 18 "N viram seu perfil"
    "linkedin@em.linkedin.com",             # 13 marketing Premium
    "notifications-noreply@linkedin.com",   # 6 impressoes de post
    "security-noreply@linkedin.com",        # 3
    "jobs-listings@linkedin.com",           # 1 vaga que ELE publicou
    "noreply@glassdoor.com",                # alerta Glassdoor
    # --- trabalho: 158 de 426 numa janela de 7 dias, o maior bloco da caixa ---
    "notifications@tasks.clickup.com",
    "notifications@clickup.com",
    "noreply@business-updates.facebook.com",
    "gitlab@mg.gitlab.com",
    # --- newsletter que fala "interview"/"vaga"/"next steps" sem ser candidatura ---
    "peter@sourceofsources.com", "value@acquisition.com",
    "marketing@cdludi.com.br", "marketing@cdludi.org.br",
    "team@news-mail.elementor.com", "team@emails.hostinger.com",
    "informativo@mec.gov.br",               # FIES: "processo seletivo" que nao e' vaga
    # --- vida pessoal ---
    "aeug-preferences09@mail.aliexpress.com", "noreply@steampowered.com",
    "howdy@fireshinegames.co.uk", "todomundo@nubank.com.br",
    "relacionamento@mail.c6bank.com.br", "contato@empresas.b3.com.br",
    "news@latampassmail.com", "latam@mails.latam.com",
    "smartfit@contato.smartfit.com", "googleplay-noreply@google.com",
    "noreply-accounts@google.com", "marketing@consumidor.reclameaqui.com.br",
    "auto@4mdg.com.br",
    # medidos na rodada de 21d: blast e newsletter, nao candidatura dele
    "torre@torre.ai", "ciadetalentos@ciadetalentos.com",
    "carreiradossonhos@ciadetalentos.com", "githubeducation@github.com",
    "welcome@supabase.com",
]

# Comparado via sem_acento(), entao escreve SEM acento aqui e cobre as duas grafias.
RUIDO_ASSUNTO = [
    "new job alert", "job alert",
    "esta contratando para um cargo", "novas vagas", "candidate-se",
    "procurando um novo emprego", "vagas recomendadas", "vagas para voce",
    "melhores vagas", "inscricoes abertas", "ultimos dias",
    # nag de plataforma: cobra acao sem ser sobre candidatura dele
    "increase your chances", "improve your rank", "increase your ranking",
    "anonymously", "what's next for", "whats next for",
    # blast de vaga da Torre e afins, formato "Full-time (remote): X at Y"
    "full-time (remote)", "freelance (remote)", "part-time (remote)",
    "one new job matching", "job matching your profi",
    # autenticacao: nao e' estado de candidatura
    "security code for your application", "log in to", "login to",
    "verify your login", "2-step verification", "security question has been",
]

# ESTADO. Primeiro que casa ganha, entao a ordem E' a prioridade.
# `OFERTA` no topo: carta proposta e' o unico e-mail que muda a vida dele.
# `EXPIRANDO` antes de entrevista: prazo vencendo vale mais que convite parado.
# A ordem E a prioridade. `rejeitada` vem ANTES de `entrevista` porque
# "agradecemos sua participacao na entrevista, optamos por outros perfis"
# tem as duas palavras, e o que importa e o desfecho.
REGRAS = [
    ("OFERTA", r"carta proposta|offer letter|job offer|we(?:'| a)re pleased to offer|"
               r"proposta de trabalho|seu perfil foi aprovado|"
               r"pacote de compensa|aceite formal|welcome to the team"),
    ("EXPIRANDO", r"final reminder|last reminder|closing soon|"
                  r"expires? (?:today|tomorrow|in \d+)|ultimo aviso|prazo final|"
                  r"interview process closing"),
    ("convite", r"invited you to (?:a job|submit a proposal)|invitation to interview for|"
                r"invites you to a (?:video )?interview|you(?:'|&#39;|&rsquo;)?ve been "
                r"invited|no connects needed|apply for free"),
    ("rejeitada", r"unfortunately|not (?:moving|proceed|selected)|"
                  r"decided to (?:move|go) (?:forward|ahead) with|other candidates|"
                  r"no longer under consideration|regret to inform|"
                  r"infelizmente|optamos por seguir com|"
                  r"seguir com outros (?:perfis|candidatos)|"
                  r"mais alinhados com (?:alguns )?crit|"
                  r"n[\u00e3a]o (?:seguiremos|prosseguir|foi|seguiu)|"
                  r"processo (?:seletivo )?(?:foi )?(?:encerrado|finalizado)|"
                  r"seguimos com outro"),
    ("entrevista", r"schedule (?:a |an )?(?:call|interview|chat)|calendly|book a time|"
                   r"interview invitation|invitation for|entrevista|agendar|"
                   r"meet\.google|zoom\.us/j/|interview reminder|meeting invite|"
                   r"event confirmation for|start your interview"),
    ("respondida", r"thank you for (?:your )?(?:application|proposal|interest)|"
                   r"received your (?:application|proposal)|next steps|"
                   r"reviewing your|recebemos sua|application received|"
                   r"update on your application|agradecemos seu interesse"),
]

# Acao que exige ele e nao muda estado de cartao.
ACAO = [
    ("ASSINAR/RESPONDER OFERTA", r"aceite formal|carta proposta|offer letter|"
                                 r"pacote de compensa"),
    ("PRAZO VENCENDO", r"final reminder|closing soon|last reminder|prazo final"),
    ("CONVITE 0 CONNECTS", r"no connects needed|apply for free"),
    ("recrutador falou", r"acabou de enviar uma mensagem|sent you a message|"
                         r"nova mensagem de"),
    ("verificar e-mail", r"verify your email|confirm your email|verifique seu e-?mail"),
    ("pediu material", r"send (?:us )?(?:a )?(?:loom|video|screen recording|screenshots|"
                       r"portfolio|case stud)|please (?:share|provide|attach)"),
    ("gravar video", r"start your interview|one-way interview|video interview|"
                     r"record your (?:answers|interview)"),
]

ORDEM = ["OFERTA", "EXPIRANDO", "convite", "entrevista", "respondida", "rejeitada",
         "EU RESPONDI", None]


def creds():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    c = None
    if os.path.exists(TOKEN):
        c = Credentials.from_authorized_user_file(TOKEN, ESCOPO)
    if c and c.expired and c.refresh_token:
        c.refresh(Request())
    if not c or not c.valid:
        if not os.path.exists(CRED):
            raise SystemExit(
                "Falta o client secret do OAuth em:\n  %s\n\n"
                "No Google Cloud Console, na MESMA conta Google da caixa que voce quer ler:\n"
                "  1. APIs e servicos > Biblioteca > ativar Gmail API\n"
                "  2. Clients > Create OAuth client > tipo Aplicativo para desktop\n"
                "  3. baixar o JSON e salvar no caminho acima\n"
                "  4. Audience > Test users > adicionar o proprio e-mail\n"
                "     (sem isso o consentimento morre em access_denied)\n" % CRED)
        flow = InstalledAppFlow.from_client_secrets_file(CRED, ESCOPO)
        c = flow.run_local_server(port=0, prompt="consent")
        os.makedirs(os.path.dirname(TOKEN), exist_ok=True)
        io.open(TOKEN, "w", encoding="utf-8").write(c.to_json())
        print("token salvo em", TOKEN)
    return c


def dominios_do_quadro():
    """Dominios das vagas ja enviadas, pro filtro crescer com o funil."""
    achados = set()
    for cam in (os.path.join(AQUI, "enviadas.json"),
                os.path.join("data", "enviadas.json")):
        if not os.path.exists(cam):
            continue
        try:
            for v in json.load(io.open(cam, encoding="utf-8")):
                m = re.search(r"https?://([^/]+)", v.get("url") or "")
                if m:
                    p = m.group(1).replace("www.", "").split(".")
                    if len(p) >= 2:
                        achados.add(".".join(p[-2:]))
        except Exception as e:
            print("  aviso: nao li %s (%s)" % (cam, str(e)[:60]))
    return achados


def texto(msg):
    """Extrai o texto legivel. Prefere text/plain; se vier curto demais cai no HTML.

    Existe porque muito e-mail de ATS manda text/plain vazio e o conteudo todo em HTML com
    CSS embutido: sem tirar <style> o classificador lia regra de CSS achando que era corpo.
    Foi o que aconteceu com a Torre.ai."""
    plano, html = [], []

    def andar(p):
        mt, d = p.get("mimeType", ""), p.get("body", {}).get("data")
        if d:
            try:
                s = base64.urlsafe_b64decode(d).decode("utf-8", "replace")
            except Exception:
                s = ""
            if mt == "text/plain":
                plano.append(s)
            elif mt == "text/html":
                html.append(s)
        for f in p.get("parts", []) or []:
            andar(f)

    andar(msg.get("payload", {}))
    t = "\n".join(plano).strip()
    if len(t) < 120 and html:
        h = "\n".join(html)
        h = re.sub(r"(?is)<(style|script|head)[^>]*>.*?</\1>", " ", h)
        h = re.sub(r"(?is)<br[^>]*>|</p>|</div>|</tr>", "\n", h)
        h = re.sub(r"(?s)<[^>]+>", " ", h)
        t = h
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&#39;", "'"), ("&rsquo;", "'"),
                 ("&quot;", '"'), ("&eacute;", "e"), ("&ccedil;", "c"),
                 ("&atilde;", "a"), ("&iacute;", "i"), ("&oacute;", "o"),
                 ("&aacute;", "a")):
        t = t.replace(a, b)
    t = re.sub(r"https?://\S+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]{2,}", " ", t)).strip()[:9000]


def classificar(t):
    t = sem_acento(t)
    estado = None
    for nome, padrao in REGRAS:
        if re.search(padrao, t):
            estado = nome
            break
    return estado, [n for n, p in ACAO if re.search(p, t)]


def varrer(dias=21):
    from googleapiclient.discovery import build
    svc = build("gmail", "v1", credentials=creds(), cache_discovery=False)

    dom = sorted(set(ATS) | dominios_do_quadro())
    print("janela %dd - %d frases OR %d dominios - menos %d remetentes de ruido"
          % (dias, len(FRASES), len(dom), len(RUIDO_DE)))
    q = "(%s OR %s) %s newer_than:%dd" % (
        " OR ".join(FRASES), " OR ".join("from:%s" % d for d in dom),
        " ".join("-from:%s" % d for d in RUIDO_DE), dias)

    achados, pg = [], None
    while True:
        r = svc.users().messages().list(userId="me", q=q, maxResults=100,
                                        pageToken=pg).execute()
        achados += r.get("messages", []) or []
        pg = r.get("nextPageToken")
        if not pg:
            break
    print("depois do corte por remetente: %d" % len(achados))

    linhas, cortadas = [], 0
    for m in achados:
        msg = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        cab = {h["name"].lower(): h["value"]
               for h in msg.get("payload", {}).get("headers", [])}
        assunto, de = cab.get("subject", ""), cab.get("from", "")
        if any(p in sem_acento(assunto) for p in RUIDO_ASSUNTO):
            cortadas += 1
            continue
        if any(e in de.lower() for e in EU):
            linhas.append((cab.get("date", "")[:22], de, assunto, "EU RESPONDI", []))
            continue
        estado, acoes = classificar(assunto + "\n" + texto(msg))
        linhas.append((cab.get("date", "")[:22], de, assunto, estado, acoes))
    print("menos %d por assunto de alerta  ->  %d mensagens de verdade"
          % (cortadas, len(linhas)))

    urgente = [l for l in linhas if l[3] in ("OFERTA", "EXPIRANDO") or l[4]]
    if urgente:
        print("\n" + "!" * 94)
        print("AGORA  -  %d mensagem(ns) esperando voce" % len(urgente))
        print("!" * 94)
        for data, de, ass, est, ac in urgente:
            print("  [%-9s] %-30s %s" % (est or "-", de[:30], ass[:44]))
            if ac:
                print("  %-11s %-30s -> %s" % ("", "", ", ".join(ac)))

    for grupo in ORDEM:
        g = [l for l in linhas if l[3] == grupo]
        if not g:
            continue
        print("\n=== %s (%d) ===" % (grupo or "sem rotulo", len(g)))
        for data, de, ass, est, ac in g:
            print("  %-22s %-32s %s" % (data, de[:32], ass[:46]))


def tudo(dias=7):
    """Varredura TOTAL da janela, sem filtro. Reaudita o padrao da caixa."""
    import collections
    from googleapiclient.discovery import build
    svc = build("gmail", "v1", credentials=creds(), cache_discovery=False)

    ids, pg = [], None
    while True:
        r = svc.users().messages().list(userId="me", q="newer_than:%dd" % dias,
                                        maxResults=500, pageToken=pg).execute()
        ids += [m["id"] for m in (r.get("messages", []) or [])]
        pg = r.get("nextPageToken")
        if not pg:
            break
    print("janela %dd - caixa inteira: %d mensagens\n" % (dias, len(ids)))

    cont, desconhecido, exemplo = collections.Counter(), collections.Counter(), {}
    for i in ids:
        m = svc.users().messages().get(userId="me", id=i, format="metadata",
                                       metadataHeaders=["From", "Subject"]).execute()
        h = {x["name"].lower(): x["value"] for x in m.get("payload", {}).get("headers", [])}
        ass, de = h.get("subject", ""), h.get("from", "")
        e = re.search(r"[\w.+-]+@[\w.-]+", de)
        e = (e.group(0) if e else de).lower()
        if any(x in de.lower() for x in EU):
            rot = "EU MANDEI"
        elif e in RUIDO_DE:
            rot = "ruido conhecido"
        elif any(p in sem_acento(ass) for p in RUIDO_ASSUNTO):
            rot = "alerta de vaga"
        else:
            est, _ = classificar(ass)
            rot = est or "desconhecido"
            if rot == "desconhecido":
                desconhecido[e] += 1
                exemplo.setdefault(e, ass)
        cont[rot] += 1

    print("=" * 94)
    print("PADRAO DA CAIXA")
    print("=" * 94)
    for rot, n in cont.most_common():
        print("  %-18s %4d  (%4.1f%%)" % (rot, n, 100.0 * n / max(1, len(ids))))

    print("\n" + "=" * 94)
    print("DESCONHECIDO por remetente  -  ruido novo ou regra que falta")
    print("=" * 94)
    for e, n in desconhecido.most_common(30):
        print("  %-4d %-40s %s" % (n, e[:40], exemplo.get(e, "")[:44]))


if __name__ == "__main__":
    _saida_utf8()
    acao = sys.argv[1] if len(sys.argv) > 1 else "varrer"
    n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else None
    if acao == "autorizar":
        creds()
        print("autorizado.")
    elif acao == "varrer":
        varrer(n or 21)
    elif acao == "tudo":
        tudo(n or 7)
    else:
        raise SystemExit(__doc__)
