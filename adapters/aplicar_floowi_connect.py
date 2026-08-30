"""Floowi Connect: entra no banco de talentos (nao e' a candidatura, e' o pool).

  python aplicar_floowi_connect.py [--submit]
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
CV = os.path.join(BASE, PERFIL["curriculos"]["web_seo"])
URL = "https://floowi.na.teamtailor.com/connect"
DO = "--submit" in sys.argv

# o label nao usa for=, o input fica DENTRO dele: pegar o texto do label ancestral
ROTULOS = """(sel) => [...document.querySelectorAll(sel)].map(e => {
    let p = e, t = '';
    for (let i = 0; i < 4 && p; i++) {
      if (p.tagName === 'LABEL' || p.getAttribute?.('role') === 'radio') {
        t = (p.innerText || '').trim(); break;
      }
      p = p.parentElement;
    }
    if (!t) t = (e.closest('div')?.innerText || '').trim();
    return {v: e.value, t: t.split('\\n')[0].slice(0, 45)};
  })"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, channel="msedge")
    pg = b.new_context(viewport={"width": 1350, "height": 1050}, locale="en-US").new_page()
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3500)
    try:
        pg.locator("button:has-text('Accept all cookies')").first.click(timeout=4000)
        pg.wait_for_timeout(1200)
    except Exception:
        pass

    deps = pg.evaluate(ROTULOS, "input[name='candidate[department_id]']")
    print("DEPARTAMENTOS:")
    for d in deps:
        print(f"   {d['v']:>8}  {d['t']}")

    alvo = next((d for d in deps if re.search(r"market|growth|digital|media", d["t"], re.I)), None)
    if not alvo:
        print("\nNao achei departamento de marketing. Abortando para nao chutar.")
        b.close(); raise SystemExit(2)
    print(f"\nescolhido: {alvo['v']} = {alvo['t']}")
    pg.evaluate("""(v) => { const e = document.querySelector(
          `input[name="candidate[department_id]"][value="${v}"]`); if (e) e.click(); }""", alvo["v"])
    pg.wait_for_timeout(2000)

    roles = pg.evaluate(ROTULOS, "input[name='candidate[role_id]']")
    quero = [r for r in roles if re.search(r"seo|paid|ads|ppc|media|growth|market|analytic", r["t"], re.I)]
    print("\nFUNCOES marcadas:")
    for r in quero[:8]:
        print(f"   {r['v']:>8}  {r['t']}")
        pg.evaluate("""(v) => { const e = document.querySelector(
              `input[name="candidate[role_id]"][value="${v}"]`); if (e && !e.checked) e.click(); }""", r["v"])
        pg.wait_for_timeout(300)

    if not DO:
        print("\nDRY-RUN: nao cliquei em Continue.")
        pg.screenshot(path=os.path.join(BASE, "_tmp", "floowi-connect.png"), full_page=True)
        b.close(); raise SystemExit(0)

    # o campo de e-mail so' existe DEPOIS do Continue: e' um wizard por etapas
    pg.locator("button:has-text('Continue')").first.click()
    pg.wait_for_timeout(6000)
    print("URL apos Continue:", pg.url)
    try:
        pg.fill("input[name='candidate[email]']", ID["email"])
        print(f"  email: {ID['email']}")
        pg.wait_for_timeout(800)
    except Exception as e:
        print("  email nesta etapa:", repr(e)[:50])

    # etapa 2: costuma pedir nome, telefone e curriculo
    for campo, valor in (("candidate[first_name]", ID["first_name"]),
                         ("candidate[last_name]", ID["last_name"]),
                         ("candidate[phone]", ID["telefone_e164"])):
        try:
            pg.fill(f"input[name='{campo}']", valor)
            print(f"  {campo} ok")
        except Exception:
            pass
    try:
        pg.locator("input[type=file]").first.set_input_files(CV)
        pg.wait_for_timeout(6000)
        print("  cv enviado")
    except Exception as e:
        print("  cv:", repr(e)[:50])
    for cid in ("candidate_consent_given", "candidate_connect_consent_given"):
        try:
            pg.locator(f"input[type=checkbox]#{cid}").check(force=True, timeout=4000)
            print(f"  {cid} ok")
        except Exception:
            pass

    pg.screenshot(path=os.path.join(BASE, "_tmp", "floowi-connect-2.png"), full_page=True)
    try:
        pg.locator("button[type=submit], input[type=submit]").last.click(timeout=8000)
        pg.wait_for_timeout(8000)
        print("URL final:", pg.url)
        corpo = pg.inner_text("body")
        print("sinais:", [l.strip() for l in corpo.split("\n")
                          if re.search(r"thank|welcome|joined|success|verify", l, re.I)][:5])
    except Exception as e:
        print("submit final:", repr(e)[:60])
    pg.screenshot(path=os.path.join(BASE, "_tmp", "floowi-connect-3.png"), full_page=True)
    b.close()
