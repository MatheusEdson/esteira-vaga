"""AtomChat · GTM Engineer (Brasil) · board da Deel.

  python aplicar_deel_atomchat.py            # dry-run
  python aplicar_deel_atomchat.py --submit    # envia
  python aplicar_deel_atomchat.py --janela    # abre preenchido para ele conferir

Decisoes registradas:
  - Ferramentas: marca SO Claude Code e N8N/Make/Zapier. NAO marca Clay, Smartlead/Lemlist
    nem HeyReach/Waalaxy: ele nao usou nenhuma das tres. Marcar seria inventar, e num cargo
    de GTM Engineer isso cai na primeira conversa tecnica.
  - Integracoes: APIS + Webhooks + nativas, os tres verdadeiros.
  - Numeros do outbound saem do Postgres da vps2b (levantamento desta semana), nao de memoria.
  - Respostas em INGLES: o formulario esta em espanhol e a vaga e para o Brasil; ingles e o
    neutro que o CV dele sustenta.
"""
import sys, os, re, time
import io
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py

BASE = os.path.dirname(os.path.abspath(__file__))
from core.perfil import perfil as _carregar_perfil   # le data/perfil.json
PERFIL = _carregar_perfil()
from core.perfil import curriculo as _cv

def bloco(chave):
    """Le uma resposta dissertativa de respostas/deel_atomchat.md.

    As respostas nao vivem no codigo porque carregam metrica de empregador e de cliente.
    respostas/ e gitignored. Sem o arquivo, ABORTA em vez de enviar formulario vazio.
    """
    from core.perfil import respostas_md
    caminho = respostas_md("deel_atomchat.md")
    if not os.path.exists(caminho):
        raise SystemExit(
            "ERRO: nao achei %s\n"
            "Crie o arquivo com uma secao por resposta:\n"
            "  ## NOME_DA_CHAVE\n  seu texto aqui\n"
            "Ver docs/respostas-formato.md." % caminho)
    txt = io.open(caminho, encoding="utf-8").read()
    m = re.search(r"^##\s+" + re.escape(chave) + r"\s*$(.*?)(?=^##\s|\Z)",
                  txt, re.M | re.S)
    if not m or not m.group(1).strip():
        raise SystemExit("ERRO: falta a secao '## %s' em %s" % (chave, caminho))
    return m.group(1).strip()

ID = PERFIL["identidade"]

def do_perfil(chave, secao="respostas_padrao"):
    """Le do perfil e ABORTA se estiver vazio.

    Existe porque estes adaptadores nasceram como script de uma candidatura so', com o
    valor real digitado inline: pretensao, ultimo salario, empregador atual. Isso publica
    a posicao de negociacao de quem usa o repo e trava o adaptador em uma pessoa so'.
    Vazio aborta de proposito: melhor parar do que mandar numero errado."""
    v = PERFIL.get(secao, {}).get(chave)
    v = str(v).strip() if v is not None else ""
    if not v:
        raise SystemExit("ERRO: preencha %s.%s no data/perfil.json" % (secao, chave))
    return v

CV = _cv("gtm_engineer")

URL = ("https://jobs.deel.com/atomchat/job-details/"
       "da6eaa1a-23f9-4a15-ac97-e32c2d865799/application")
SUBMIT = "--submit" in sys.argv
JANELA = "--janela" in sys.argv

TEXTOS = {
    "firstName":          ID["first_name"],
    "lastName":           ID["last_name"],
    "email":              ID["email"],
    "phoneNumber":        ID.get("telefone_e164", "").lstrip("+"),
    "linkedinProfileUrl": ID["linkedin_url"],
}

# checkboxes por TEXTO do rotulo (o form nao da name/id nos checkboxes)
MARCAR = [
    "Claude Code",
    "N8N, Make, Zapier",
    "APIS",
    "Webhooks",
    "Integraciones nativas (HubSpot, Slack, etc.)",
]
NAO_MARCAR = ["Clay", "Smartlead / Lemlist", "HeyReach / Waalaxy",
              "Ninguna de las anteriores", "Ninguno"]

# GOTCHA CARO: as dissertativas tem limite de 500 CARACTERES, e o campo NAO declara
# maxLength. Ele aceita o texto inteiro em silencio, marca aria-invalid=true sem mostrar
# mensagem no campo, e o botao Apply fica disabled para sempre. Achado por bissecao:
# 498 chars = valido, 598 = invalido.
OUTBOUND_DESAFIO = bloco("OUTBOUND_DESAFIO")

OUTBOUND_SOZINHO = bloco("OUTBOUND_SOZINHO")

for _nome, _txt in (("OUTBOUND_DESAFIO", OUTBOUND_DESAFIO), ("OUTBOUND_SOZINHO", OUTBOUND_SOZINHO)):
    if len(_txt) > 500:
        raise SystemExit("ERRO: %s tem %d chars, limite do campo e 500" % (_nome, len(_txt)))

ANOS_GTM = bloco("ANOS_GTM")

SALARIO_ESPERADO = do_perfil("expected_salary_usd_month")
ULTIMA_REMUNERACAO = do_perfil("ultima_remuneracao_usd")
# GOTCHA: o campo de preaviso e inputmode=numeric com min=10 e max=100, ou seja espera
# DIAS, nao texto. "2 weeks" virava "2" e seria rejeitado por ficar abaixo do minimo.
PREAVISO = "14"

if not os.path.exists(CV):
    raise SystemExit("ERRO: nao achei " + CV)


def marca_checkbox(pg, texto, estado=True):
    return pg.evaluate("""([txt, quer]) => {
        const alvo = txt.trim().toLowerCase();
        const cbs = [...document.querySelectorAll('input[type=checkbox]')];
        for (const c of cbs) {
          let lb = '';
          const l = document.querySelector('label[for="' + (c.id||'x').replace(/"/g,'') + '"]');
          if (l) lb = l.innerText.trim();
          if (!lb && c.closest('label')) lb = c.closest('label').innerText.trim();
          if (!lb) {
            const w = c.closest('div');
            if (w) lb = (w.innerText || '').trim();
          }
          if (lb.trim().toLowerCase() === alvo) {
            if (c.checked !== quer) c.click();
            return c.checked;
          }
        }
        return 'nao encontrado';
      }""", [texto, estado])


with sync_playwright() as p:
    b = p.chromium.launch(headless=not JANELA, channel="msedge",
                          )
    ctx = b.new_context(viewport={"width": 1400, "height": 1400}, locale="en-US")
    pg = ctx.new_page()

    rede = []
    pg.on("request", lambda r: rede.append(("REQ", r.method, r.url[:120]))
          if r.method in ("POST", "PUT", "PATCH") else None)
    pg.on("response", lambda r: rede.append(("RES", str(r.status), r.url[:120]))
          if r.request.method in ("POST", "PUT", "PATCH") else None)

    print("[1]", URL[:90])
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(11000)

    # ORDEM IMPORTA: o CV sobe PRIMEIRO. A Deel roda um parser no PDF e SOBRESCREVE
    # firstName/lastName. Preenchendo antes, o sobrenome vinha com o nome do meio junto.
    print("[2] curriculo (PDF obrigatorio) - antes dos textos, de proposito")
    try:
        pg.locator("input[type=file]").first.set_input_files(CV)
        pg.wait_for_timeout(7000)
        print("   anexado:", os.path.basename(CV))
    except Exception as ex:
        print("   FALHOU:", str(ex)[:120])

    print("[3] campos de texto (sobrescrevendo o que o parser preencheu)")
    for nome, valor in TEXTOS.items():
        ok = False
        for sel in (f"input[name='{nome}']", f"[name='{nome}']"):
            try:
                el = pg.locator(sel).first
                el.wait_for(state="visible", timeout=5000)
                el.fill("")
                el.fill(valor)
                ok = True
                break
            except Exception:
                continue
        lido = pg.evaluate("""(n) => { const e = document.querySelector('[name="'+n+'"]');
                                       return e ? e.value : '(ausente)'; }""", nome)
        marca = "" if lido.strip() == valor.strip() else "  <-- DIVERGIU"
        print(f"   {nome:<20} {'ok' if ok else 'FALHOU':<7} {lido[:52]}{marca}")

    print("[3b] dial code (combobox com autocomplete, nao aceita fill puro)")
    try:
        dc = pg.locator("[name='phoneNumber_dialCode']").first
        dc.click()
        pg.wait_for_timeout(800)
        pg.keyboard.type("Brazil", delay=110)
        pg.wait_for_timeout(1600)
        opcoes = pg.evaluate("""() => [...document.querySelectorAll('[role=option], li')]
              .map(e => (e.innerText||'').trim()).filter(t => /brazil|\\+55/i.test(t)).slice(0,5)""")
        print("   opcoes vistas:", opcoes)
        pg.keyboard.press("ArrowDown")
        pg.wait_for_timeout(300)
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(900)
    except Exception as ex:
        print("   erro:", str(ex)[:110])
    print("   dial code =", pg.evaluate(
        """() => { const e = document.querySelector("[name='phoneNumber_dialCode']");
                   return e ? e.value : '(ausente)'; }"""))

    print("[4] checkboxes que MARCAM")
    for t in MARCAR:
        print(f"   {str(marca_checkbox(pg, t, True)):<14} {t}")
    print("[4b] checkboxes que ficam DESMARCADOS (conferencia)")
    for t in NAO_MARCAR:
        r = pg.evaluate("""(txt) => {
            const alvo = txt.trim().toLowerCase();
            for (const c of document.querySelectorAll('input[type=checkbox]')) {
              let lb = '';
              const l = document.querySelector('label[for="' + (c.id||'x').replace(/"/g,'') + '"]');
              if (l) lb = l.innerText.trim();
              if (!lb && c.closest('label')) lb = c.closest('label').innerText.trim();
              if (!lb) { const w = c.closest('div'); if (w) lb = (w.innerText||'').trim(); }
              if (lb.trim().toLowerCase() === alvo) return c.checked ? 'MARCADO (ERRO)' : 'ok, vazio';
            }
            return 'nao encontrado'; }""", t)
        print(f"   {r:<16} {t}")

    print("[5] respostas longas, casadas por ID exato do campo")
    # DOIS GOTCHAS aprendidos aqui:
    # 1) O form da Deel e React e IGNORA `e.value = x` setado por script. Tem que ser o
    #    fill() do Playwright, que dispara os eventos que o React escuta.
    # 2) Casar por texto de ancestral NAO funciona: subindo o DOM voce chega num ancestral
    #    que contem o formulario inteiro, entao TODO campo "casa" com a primeira regex.
    #    O casamento certo e por ID, que veio do recon.
    CAMPOS_LONGOS = [
        ("03f2b762-cd6d-49b6-917d-49083e408ca9", OUTBOUND_DESAFIO,   "outbound desafiante"),
        ("91dc9929-f3a0-4862-ac18-65e2042ccee6", ANOS_GTM,           "anos em GTM"),
        ("ccc45345-5787-452b-a99d-727257c695db", OUTBOUND_SOZINHO,   "outbound 100% sozinho"),
        ("ccb6e39f-c458-4f0a-9593-a05ec7c2a7d6", SALARIO_ESPERADO,   "expectativa salarial USD"),
        ("f755dd67-8ad4-4461-84c3-a00e414ec9be", ULTIMA_REMUNERACAO, "ultima remuneracao USD"),
        ("19aa7696-0460-4e72-98a6-396fa6f5dbb3", PREAVISO,           "preaviso"),
    ]
    for fid, valor, rotulo in CAMPOS_LONGOS:
        ok = False
        for sel in ("[name='%s']" % fid, "[id='%s']" % fid):
            try:
                el = pg.locator(sel).first
                el.wait_for(state="visible", timeout=4000)
                el.fill(valor)
                ok = True
                break
            except Exception:
                continue
        lido = pg.evaluate("""(f) => {
            const e = document.querySelector('[name="'+f+'"], [id="'+f+'"]');
            return e ? (e.value || '').slice(0, 60) : '(ausente)'; }""", fid)
        print("   %-24s %-7s | gravado: %s" % (rotulo, "ok" if ok else "FALHOU", lido))

    print("[5a] repasse: MUI valida no blur e as vezes deixa campo preenchido como invalido")
    VALORES = {fid: v for fid, v, _ in CAMPOS_LONGOS}
    for tentativa in (1, 2):
        ruins = pg.evaluate("""() => [...document.querySelectorAll('input,textarea')]
              .filter(e => e.getAttribute('aria-invalid') === 'true' && (e.value||'').trim())
              .map(e => e.name || e.id)""")
        if not ruins:
            print("   passe %d: nada invalido" % tentativa)
            break
        print("   passe %d: reprocessando %s" % (tentativa, [r[:8] for r in ruins]))
        for fid in ruins:
            if fid not in VALORES:
                continue
            try:
                el = pg.locator("[name='%s']" % fid).first
                el.click()
                el.fill("")
                pg.wait_for_timeout(250)
                el.fill(VALORES[fid])
                pg.keyboard.press("Tab")
                pg.wait_for_timeout(700)
            except Exception as ex:
                print("      erro em %s: %s" % (fid[:8], str(ex)[:60]))

    print("[5b] consentimento de privacidade (mantem o Apply DESABILITADO se faltar)")
    # O ultimo checkbox do form e o aceite da politica de privacidade. No recon o rotulo
    # dele resolveu errado como "First name *", entao passou batido e o botao Apply ficava
    # disabled=true para sempre.
    # O aceite e o ULTIMO checkbox do form e nao tem rotulo nenhum (fica ao lado do link
    # "privacy policy"). Casar por texto e impossivel, entao vai por indice: os 10 primeiros
    # sao as duas perguntas de ferramentas/integracao, o 11o e o consentimento.
    total = pg.locator("input[type=checkbox]").count()
    print("   checkboxes no form:", total)
    if total >= 11:
        r = pg.evaluate("""() => {
            const cbs = [...document.querySelectorAll('input[type=checkbox]')];
            const c = cbs[cbs.length - 1];
            if (!c.checked) c.click();
            return c.checked; }""")
        print("   consentimento (ultimo checkbox, sem rotulo) =", r)
    else:
        print("   ATENCAO: esperava >=11 checkboxes, achei", total)

    est = pg.evaluate("""() => [...document.querySelectorAll('button')]
        .filter(b => /apply/i.test(b.innerText || ''))
        .map(b => { const r = b.getBoundingClientRect();
            return {disabled: !!b.disabled, visivel: r.width > 0 && r.height > 0}; })""")
    print("   estado dos botoes Apply:", est)

    print("[5c] o que o form considera INVALIDO ou vazio")
    inval = pg.evaluate("""() => {
        const out = [];
        document.querySelectorAll('input,textarea,select').forEach(e => {
          if (['hidden','submit','button','image'].includes(e.type)) return;
          const ruim = e.getAttribute('aria-invalid') === 'true';
          const vazio = (e.type === 'checkbox') ? false : !(e.value || '').trim();
          const arquivo = e.type === 'file' ? !(e.files && e.files.length) : false;
          if (ruim || vazio || arquivo) {
            let lab = '', q = e.closest('div,li,fieldset,label');
            for (let i = 0; i < 8 && q; i++) {
              const l = q.querySelector('label,legend');
              if (l && l.innerText && l.innerText.trim().length > 2) { lab = l.innerText.trim(); break; }
              q = q.parentElement;
            }
            out.push({campo: (e.name || e.id || e.tagName).slice(0, 34), tipo: e.type,
                      invalido: ruim, vazio: vazio || arquivo,
                      rotulo: lab.replace(/\\s+/g, ' ').slice(0, 70)});
          }
        });
        return out; }""")
    for x in inval:
        print("   %-34s tipo=%-9s invalido=%-5s vazio=%-5s | %s" %
              (x["campo"], x["tipo"], x["invalido"], x["vazio"], x["rotulo"]))
    if not inval:
        print("   (nada invalido nem vazio)")

    print("[5d] mensagens de erro/ajuda visiveis")
    for m in pg.evaluate("""() => [...document.querySelectorAll('p,span,div')]
          .filter(e => e.children.length === 0 &&
                       /required|obligator|invalid|error|debe|falta/i.test(e.textContent || ''))
          .map(e => (e.textContent || '').trim().slice(0, 90)).slice(0, 12)"""):
        print("   -", m)

    print("\n[6] ESTADO FINAL")
    for l in pg.evaluate("""() => {
          const vis = e => { const r = e.getBoundingClientRect(); return r.width>0 && r.height>0; };
          const out = [];
          document.querySelectorAll('input,textarea,select').forEach(e => {
            if (['hidden','submit','button','image'].includes(e.type)) return;
            if (e.type === 'checkbox') { if (e.checked) out.push('[x] ' + ((e.closest('label')||e.closest('div')||{}).innerText||'').replace(/\\s+/g,' ').trim().slice(0,60)); return; }
            if (!vis(e)) return;
            let v = e.value || '';
            if (e.type === 'file') v = e.files && e.files.length ? e.files[0].name : '(sem arquivo)';
            out.push((e.name || e.id || e.tagName).slice(0,26) + ' = ' + String(v).slice(0,74));
          });
          return out; }"""):
        print("   ", l)

    pg.screenshot(path=os.path.join(BASE, "_tmp", "deel-atom-preenchido.png"), full_page=True)

    if JANELA:
        print("\nJANELA ABERTA. Confira e clique em Apply.")
        while len(ctx.pages) > 0:
            time.sleep(5)
    elif SUBMIT:
        print("\n[7] ENVIANDO")
        # GOTCHA: existem DOIS botoes "Apply". O .last e invisivel, entao usar .last fazia
        # o loop desistir. O certo e o primeiro VISIVEL e HABILITADO.
        clic = False
        botoes = pg.locator("button", has_text="Apply")
        for i in range(botoes.count()):
            bt = botoes.nth(i)
            try:
                if not bt.is_visible():
                    print(f"   Apply #{i}: invisivel, pulando")
                    continue
                if bt.is_disabled():
                    print(f"   Apply #{i}: DESABILITADO, falta campo obrigatorio")
                    continue
                bt.scroll_into_view_if_needed()
                pg.wait_for_timeout(900)
                print(f"   Apply #{i}: clicando")
                bt.click()
                clic = True
                break
            except Exception as ex:
                print(f"   Apply #{i}: erro {str(ex)[:70]}")
        if not clic:
            print("   NENHUM BOTAO DE ENVIO CLICAVEL")
        for i in range(14):
            pg.wait_for_timeout(3000)
            corpo = pg.inner_text("body")
            ok = re.search(r"thank you|thanks|submitted|received|success|gracias|recibid", corpo, re.I)
            err = [l.strip() for l in corpo.split("\n")
                   if re.search(r"required|obligatorio|invalid|error", l, re.I) and len(l.strip()) < 110]
            print(f"   t={3*(i+1):>2}s sucesso={bool(ok)} erros={err[:2]}")
            if ok:
                break
        print("   URL final:", pg.url[:120])
        print("\n   --- rede (prova de envio) ---")
        for t in rede:
            if not any(x in t[2] for x in ("google", "sentry", "hotjar", "segment", "intercom")):
                print("   ", t)
        pg.screenshot(path=os.path.join(BASE, "_tmp", "deel-atom-enviado.png"), full_page=True)
    else:
        print("\n[7] DRY-RUN: nada enviado.")

    ctx.close()
    b.close()
