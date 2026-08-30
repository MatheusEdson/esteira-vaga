"""Floowi · Senior SEO Strategist (Teamtailor com campos fora do padrao).

  python aplicar_floowi.py [--submit]

Particularidades tratadas aqui:
- salario e' um input[type=range] (slider), nao caixa de texto
- "quais ferramentas" e' multipla escolha por checkbox
- existe um campo `full_email` "Email address without domain": e' HONEYPOT
  anti-spam. Preencher REPROVA a candidatura. Fica vazio de proposito.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.bootstrap import ID, cv, bloco, tmp, sync_playwright

CV = cv("web_seo")
URL = "https://floowi.na.teamtailor.com/jobs/682828-senior-seo-strategist"
DO_SUBMIT = "--submit" in sys.argv

HTML_CSS_JS = bloco("HTML_CSS_JS")
AI_TOOLS = bloco("AI_TOOLS")
GEO = (
    "Yes, and I want to be precise about the measurement rather than overstate it. I implemented a GEO "
    "layer across an agency portfolio and my own properties: llms.txt, entity disambiguation, and "
    "structured data that describes relationships between the organization, its services and its locations "
    "rather than decorating the page. The goal was to be resolvable and citable, not to rank. The result I "
    "can verify is qualitative: assistants now resolve the brands as the correct entity, where previously "
    "one client was being confused with a similarly named company. I do not yet have clean attribution for "
    "AI-sourced sessions, and I would rather tell you that than hand you a number I cannot defend."
)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, channel="msedge")
    ctx = b.new_context(viewport={"width": 1400, "height": 1100}, locale="en-US")
    pg = ctx.new_page()
    print("[1]", URL)
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(3000)
    for sel in ["button:has-text('Accept all')", "button:has-text('Accept')"]:
        try:
            bt = pg.locator(sel).first
            if bt.is_visible(timeout=2500):
                bt.click(); pg.wait_for_timeout(1000); break
        except Exception:
            pass
    try:
        pg.locator("button:has-text('APPLY')").first.click(timeout=15000)
    except Exception:
        pass
    pg.wait_for_selector("input[name='candidate[first_name]']", timeout=60000)
    pg.wait_for_timeout(1500)

    print("[2] respostas")
    campos = {
        "candidate[answers_attributes][0][text]": "Brazil",
        "candidate[answers_attributes][3][number]": "3",
        "candidate[answers_attributes][4][text]": HTML_CSS_JS,
        "candidate[answers_attributes][5][text]": AI_TOOLS,
        "candidate[answers_attributes][6][text]": GEO,
    }
    for nome, valor in campos.items():
        pg.fill(f"[name='{nome}']", valor)
        print(f"   {nome.split('][')[1]}: {valor[:52]}...")

    print("[3] salario (slider)")
    info = pg.evaluate("""() => { const e = document.querySelector(
          'input[name="candidate[answers_attributes][1][range]"]');
        return e ? {min: e.min, max: e.max, step: e.step, val: e.value} : null; }""")
    print("   range:", info)
    r = pg.evaluate("""(alvo) => {
        const e = document.querySelector('input[name="candidate[answers_attributes][1][range]"]');
        if (!e) return 'ausente';
        const min = +e.min || 0, max = +e.max || 100;
        e.value = Math.min(Math.max(alvo, min), max);
        e.dispatchEvent(new Event('input', {bubbles: true}));
        e.dispatchEvent(new Event('change', {bubbles: true}));
        return e.value;
      }""", 3000)
    print("   valor:", r)

    print("[4] ingles = Advanced - C1")
    pg.evaluate("""() => { const e = document.querySelector(
          'input[name="candidate[answers_attributes][2][choice]"][value="2"]');
        if (e) e.click(); }""")

    print("[5] ferramentas: so' as que ele usa de fato")
    # 1 Search Console, 2 Google Analytics. SEMrush/Screaming Frog/Moz NAO.
    for v in ("1", "2"):
        pg.evaluate("""(v) => { const e = document.querySelector(
              `input[name="candidate[answers_attributes][7][choices][]"][value="${v}"]`);
            if (e && !e.checked) e.click(); }""", v)
    print("   Search Console + Google Analytics")

    print("[6] dados pessoais e curriculo")
    for campo, valor in (("first_name", ID["first_name"]), ("last_name", ID["last_name"]),
                         ("email", ID["email"]), ("phone", ID["telefone_e164"])):
        pg.fill(f"input[name='candidate[{campo}]']", valor)
    pg.locator("input[type=file]").first.set_input_files(CV)
    for i in range(15):
        pg.wait_for_timeout(2000)
        if pg.evaluate("""() => { const e = document.querySelector(
              'input[name="candidate[resume_remote_url]"]'); return !!(e && e.value); }"""):
            print(f"   cv confirmado em {2*(i+1)}s")
            break

    print("[7] consentimento")
    # neste Teamtailor o `checked = true` por JS passa despercebido pela validacao
    # e o form devolve "Must be accepted". Precisa de clique confiavel do Playwright.
    # o Rails renderiza um hidden com o MESMO name antes do checkbox real: filtrar
    # por type=checkbox, senao o check() acerta o hidden e nada acontece.
    alvo = pg.locator("input[type=checkbox][name='candidate[consent_given]']")
    print("   checkboxes com esse name:", alvo.count())
    for tent in ("check", "click", "label"):
        try:
            if tent == "check":
                alvo.first.check(force=True, timeout=8000)
            elif tent == "click":
                alvo.first.click(force=True, timeout=8000)
            else:
                # clicar na BORDA ESQUERDA do label, longe do link de Privacy Policy
                lb = pg.locator("label:has(input[name='candidate[consent_given]'])").first
                lb.click(position={"x": 6, "y": 8}, timeout=8000)
        except Exception as e:
            print(f"   {tent} falhou: {repr(e)[:45]}")
        st = pg.evaluate("""() => { const e = document.querySelector(
              'input[type=checkbox][name="candidate[consent_given]"]');
            return e ? e.checked : 'ausente'; }""")
        print(f"   apos {tent}: {st}")
        if st is True:
            break

    honey = pg.evaluate("""() => { const e = document.querySelector('input[name="full_email"]');
        return e ? (e.value || '(vazio, correto)') : '(nao existe)'; }""")
    print("   honeypot full_email:", honey)

    pg.screenshot(path=tmp("floowi-preenchido.png"), full_page=True)

    if DO_SUBMIT:
        print("\n[8] ENVIANDO")
        bt = pg.locator("input[type=submit][value*='Submit'], button[type=submit]").first
        bt.scroll_into_view_if_needed()
        pg.wait_for_timeout(1000)
        bt.click()
        for i in range(10):
            pg.wait_for_timeout(3000)
            corpo = pg.inner_text("body")
            ok = re.search(r"thank you|verify your email|application (was )?(submitted|received)", corpo, re.I)
            erro = [l.strip() for l in corpo.split("\n")
                    if re.search(r"is required|can.t be blank|invalid|error", l, re.I)]
            print(f"   t={3*(i+1):>2}s sucesso={bool(ok)} erros={erro[:3]}")
            if ok:
                break
        print("   URL:", pg.url)
        pg.screenshot(path=tmp("floowi-enviado.png"), full_page=True)
    else:
        print("\n[8] DRY-RUN: nada enviado.")

    ctx.close()
    b.close()
