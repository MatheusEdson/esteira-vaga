"""CloudWalk · Technical SEO & AI Growth Builder. Formulario Webflow proprio.

  python aplicar_cloudwalk.py            -> preenche e confere, NAO envia
  python aplicar_cloudwalk.py --submit   -> envia
"""
import sys, os, json, re
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py

BASE = os.path.dirname(os.path.abspath(__file__))
PERFIL = json.load(open(os.path.join(BASE, "perfil.json"), encoding="utf-8"))
ID = PERFIL["identidade"]
RESP = PERFIL["respostas_padrao"]


def obrigatorio(chave):
    """Aborta em vez de inventar. Vale sobretudo para o empregador atual: o nome dele
    NAO entra em candidatura, e deixar um literal no codigo publica o vinculo no repo."""
    v = (RESP.get(chave) or "").strip()
    if not v:
        raise SystemExit("ERRO: preencha respostas_padrao.%s no data/perfil.json" % chave)
    return v
DO_SUBMIT = "--submit" in sys.argv
URL = "https://www.cloudwalk.io/jobs-positions/technical-seo-ai-growth-builder-a495bf74#form-job-application"


def secao(md, titulo):
    """Extrai uma secao do respostas-cloudwalk.md pelo cabecalho."""
    txt = open(os.path.join(BASE, md), encoding="utf-8").read()
    blocos = re.split(r"\n## ", txt)
    for b in blocos:
        if b.strip().startswith(titulo):
            corpo = b.split("\n", 1)[1]
            corpo = corpo.split("\n---")[0]
            return corpo.strip()
    raise SystemExit(f"ERRO: nao achei a secao '{titulo}'")


CAMPOS = {
    "Full-name": ID["nome_completo"],
    "Email": ID["email"],
    "Phone": ID["telefone_formatado"],
    "Current-location": "%s, %s, %s" % (ID["cidade"], ID["estado"], ID["pais"]),
    "Current-company": obrigatorio("empregador_atual_nome"),
    "LinkedIn-URL": ID["linkedin_url"],
    "Other-URL": ID["portfolio"][0],
    "Exceptional-Work": secao("respostas-cloudwalk.md", "1."),
    "Tech-learned": secao("respostas-cloudwalk.md", "2."),
    "AI-tools-used": secao("respostas-cloudwalk.md", "3."),
}
RADIOS = {"English-level": "Fluent", "Portuguese-level": "Fluent"}
CHECKS = ["Agree-check", "Visa-issuence-check"]

if ID["linkedin_url"] == "PENDENTE_CONFIRMAR":
    raise SystemExit("ERRO: LinkedIn URL e' obrigatorio nesse form e esta pendente no perfil.json")

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, channel="msedge")
    ctx = b.new_context(viewport={"width": 1440, "height": 1200}, locale="en-US")
    pg = ctx.new_page()
    print("[1]", URL)
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(4000)
    for sel in ["button:has-text('Accept')", "button:has-text('Aceitar')", "button:has-text('OK')"]:
        try:
            bt = pg.locator(sel).first
            if bt.is_visible(timeout=1200):
                bt.click(); pg.wait_for_timeout(700); break
        except Exception:
            pass

    print("[2] preenchendo")
    for nome, valor in CAMPOS.items():
        try:
            el = pg.locator(f"[name='{nome}']").first
            el.scroll_into_view_if_needed()
            el.fill(str(valor))
            print(f"   {nome:<20} {str(valor)[:64].replace(chr(10),' ')}"
                  f"{'  (' + str(len(str(valor))) + ' chars)' if len(str(valor)) > 64 else ''}")
        except Exception as e:
            print(f"   {nome:<20} FALHOU {repr(e)[:60]}")

    print("[3] radios")
    for nome, valor in RADIOS.items():
        r = pg.evaluate("""([n, v]) => { const el = document.querySelector(`input[name="${n}"][value="${v}"]`);
              if (!el) return 'ausente'; el.click(); return el.checked; }""", [nome, valor])
        print(f"   {nome} = {valor}: {r}")

    print("[4] checkboxes obrigatorios")
    for nome in CHECKS:
        r = pg.evaluate("""(n) => { const el = document.querySelector(`input[name="${n}"]`);
              if (!el) return 'ausente'; if (!el.checked) el.click();
              el.dispatchEvent(new Event('change', {bubbles:true})); return el.checked; }""", nome)
        print(f"   {nome}: {r}")

    print("\n[5] conferencia")
    estado = pg.evaluate("""() => {
      const g = n => { const e = document.querySelector(`[name="${n}"]`); return e ? e.value.length : -1; };
      const rad = n => { const e = document.querySelector(`input[name="${n}"]:checked`); return e ? e.value : '(nada)'; };
      const chk = n => { const e = document.querySelector(`input[name="${n}"]`); return e ? e.checked : 'ausente'; };
      return {
        nome: document.querySelector('[name="Full-name"]').value,
        email: document.querySelector('[name="Email"]').value,
        linkedin: document.querySelector('[name="LinkedIn-URL"]').value,
        chars_q1: g('Exceptional-Work'), chars_q2: g('Tech-learned'), chars_q3: g('AI-tools-used'),
        ingles: rad('English-level'), portugues: rad('Portuguese-level'),
        agree: chk('Agree-check'), visa: chk('Visa-issuence-check'),
      };
    }""")
    for k, v in estado.items():
        print(f"   {k:>10}: {v}")

    pg.screenshot(path=os.path.join(BASE, "_tmp", "cloudwalk-preenchido.png"), full_page=True)

    if DO_SUBMIT:
        print("\n[6] ENVIANDO")
        sb = pg.locator("input[type=submit], button:has-text('SUBMIT APPLICATION')").first
        sb.scroll_into_view_if_needed()
        sb.click()
        pg.wait_for_timeout(10000)
        corpo = pg.inner_text("body")
        sinais = [l.strip() for l in corpo.split("\n")
                  if re.search(r"thank|success|received|sucesso|obrigad|error|erro|try again|required", l, re.I)]
        print("   URL:", pg.url)
        print("   sinais:", sinais[:10])
        pg.screenshot(path=os.path.join(BASE, "_tmp", "cloudwalk-enviado.png"), full_page=True)
    else:
        print("\n[6] DRY-RUN: nada enviado. Use --submit.")

    ctx.close()
    b.close()
