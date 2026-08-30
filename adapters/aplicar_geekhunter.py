"""Adaptador GeekHunter (www.geekhunter.com).

  python aplicar_geekhunter.py nava [--submit]

Dry-run por padrao: preenche, imprime o estado de cada campo e nao envia.
"""
import sys, os, json, re
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py

BASE = os.path.dirname(os.path.abspath(__file__))
from core.perfil import perfil as _carregar_perfil   # le data/perfil.json
PERFIL = _carregar_perfil()
from core.perfil import curriculo as _cv, anexo as _anexo, respostas_md as _resp
ID = PERFIL["identidade"]
RESP = PERFIL["respostas_padrao"]

VAGAS = {
    "nava": ("Nava · Backend Node.js Senior",
             "https://www.geekhunter.com/pt/nava-technology-for-business-1/jobs/"
             "desenvolvedor-a--backend-node-js-senior-1?utm_source=linkedin"
             "&utm_medium=geekhunter&utm_campaign=65642",
             "dev_fullstack"),
}

if len(sys.argv) < 2 or sys.argv[1] not in VAGAS:
    raise SystemExit(__doc__)
chave = sys.argv[1]
NOME, URL, CV_KEY = VAGAS[chave]
CV = _cv(CV_KEY)
DO_SUBMIT = "--submit" in sys.argv

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, channel="msedge")
    ctx = b.new_context(viewport={"width": 1400, "height": 1100}, locale="pt-BR")
    pg = ctx.new_page()
    print(f"[1] {NOME}\n    {URL[:100]}")
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(5000)
    for sel in ["button:has-text('Aceitar')", "button:has-text('Candidatar')",
                "a:has-text('Candidatar')", "button:has-text('Quero me candidatar')"]:
        try:
            bt = pg.locator(sel).first
            if bt.is_visible(timeout=1800):
                bt.click(); pg.wait_for_timeout(3000); break
        except Exception:
            pass

    print("[2] campos de texto")
    campos = {
        "name": ID["nome_completo"],
        "email": ID["email"],
        "confirmEmail": ID["email"],
        "linkedin": ID["linkedin_url"],
    }
    for nome, valor in campos.items():
        ok = False
        for sel in (f"input[name='{nome}']", f"textarea[name='{nome}']"):
            try:
                el = pg.locator(sel).first
                el.wait_for(state="visible", timeout=6000)
                el.fill(valor)
                ok = True
                break
            except Exception:
                continue
        print(f"   {nome}: {valor if ok else 'NAO PREENCHIDO'}")

    # o telefone e' input internacional mascarado: fill() nao passa do "+55"
    print("[2b] telefone (mascarado)")
    try:
        tel = pg.locator("input[name='phone'], input[type=tel]").first
        tel.click()
        tel.press_sequentially(ID.get("telefone_e164", "").lstrip("+"), delay=70)
        pg.wait_for_timeout(600)
        print("   phone =", tel.input_value())
    except Exception as e:
        print("   phone FALHOU:", repr(e)[:60])

    # campo de moeda com mascara: fill() quebra, tem que digitar
    print("[3] pretensao (CLT, campo mascarado)")
    try:
        sal = pg.locator("input[name='salaryExpectation.CLT'], "
                         "input[name*='salaryExpectation']").first
        if sal.count():
            sal.fill("")
            pg.wait_for_timeout(300)
            sal.press_sequentially(str(RESP["expected_salary_brl_month"]), delay=60)
            pg.wait_for_timeout(600)
            print("   salaryExpectation =", sal.input_value())
        else:
            print("   salaryExpectation: ausente")
    except Exception as e:
        print("   salario FALHOU:", repr(e)[:60])

    print("[4] curriculo")
    try:
        pg.locator("input[type=file]").first.set_input_files(CV)
        pg.wait_for_timeout(6000)
        print("   ", os.path.basename(CV))
    except Exception as e:
        print("   FALHOU:", repr(e)[:60])

    print("[5] consentimento")
    try:
        for cb in pg.locator("input[type=checkbox]").all():
            try:
                cb.check(force=True, timeout=2500)
            except Exception:
                cb.dispatch_event("click")
            print("   checkbox ->", cb.is_checked())
    except Exception as e:
        print("   FALHOU:", repr(e)[:60])

    print("[6] ESTADO FINAL")
    estado = pg.evaluate("""() => {
      const out = [];
      document.querySelectorAll('input, textarea, select').forEach(e => {
        if (e.type === 'hidden') return;
        const v = (e.type === 'checkbox' || e.type === 'radio')
          ? String(e.checked) : (e.value || '').slice(0, 46);
        out.push(`${(e.name || e.id || e.type).slice(0, 28)} = ${v}`);
      });
      return out;
    }""")
    for l in estado:
        print("   ", l)

    print("\n[7] rotulos obrigatorios detectados")
    labs = pg.evaluate("""() => {
      const out = [];
      document.querySelectorAll('label, p, span, div').forEach(e => {
        const t = (e.innerText || '').trim();
        if (/\\*/.test(t) && t.length < 120 && e.children.length < 3) out.push(t);
      });
      return [...new Set(out)].slice(0, 20);
    }""")
    for l in labs:
        print("   -", l.replace("\n", " ")[:110])

    pg.screenshot(path=os.path.join(BASE, "_tmp", f"geekhunter-{chave}.png"), full_page=True)

    if DO_SUBMIT:
        print("\n[8] ENVIANDO")
        bt = pg.locator("button[type=submit], button:has-text('Enviar'), "
                        "button:has-text('Candidatar')").last
        bt.scroll_into_view_if_needed()
        pg.wait_for_timeout(1000)
        bt.click()
        for i in range(10):
            pg.wait_for_timeout(3000)
            corpo = pg.inner_text("body")
            ok = re.search(r"obrigad|sucesso|recebemos|candidatura enviada|thank", corpo, re.I)
            erro = [l.strip() for l in corpo.split("\n")
                    if re.search(r"obrigat|inv[aá]lid|erro|required", l, re.I)]
            print(f"   t={3*(i+1):>2}s sucesso={bool(ok)} erros={erro[:3]}")
            if ok:
                break
        print("   URL:", pg.url)
        pg.screenshot(path=os.path.join(BASE, "_tmp", f"geekhunter-{chave}-enviado.png"),
                      full_page=True)
    else:
        print("\n[8] DRY-RUN: nada enviado.")

    ctx.close(); b.close()
