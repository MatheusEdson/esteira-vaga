"""Checa se uma vaga esta viva e se o formulario exige gravacao ou login.

  python checar_vagas.py <url> [<url> ...]
"""
import sys, re
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py

URLS = sys.argv[1:]
if not URLS:
    raise SystemExit(__doc__)

MORTA = r"no longer available|position has been filled|not found|no longer accepting|expired"
LOGIN = r"sign in to apply|log in to apply|create account to apply|candidates/signin"
GRAVA = r"vocaroo|loom|record a (\d+[- ])?(second|minute|min)|video introduction|record a video|voice recording"

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, channel="msedge")
    ctx = b.new_context(viewport={"width": 1300, "height": 1000}, locale="en-US")
    for url in URLS:
        pg = ctx.new_page()
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=50000)
            pg.wait_for_timeout(3000)
            for sel in ["a:has-text('Apply')", "button:has-text('Apply')"]:
                try:
                    bt = pg.locator(sel).first
                    if bt.is_visible(timeout=1500):
                        bt.click(); pg.wait_for_timeout(3500); break
                except Exception:
                    pass
            corpo = pg.inner_text("body")
            titulo = pg.title()[:72]
            campos = pg.evaluate("""() => document.querySelectorAll(
                'input[type=text],input[type=email],textarea').length""")
            morta = bool(re.search(MORTA, corpo, re.I))
            login = bool(re.search(LOGIN, corpo + pg.url, re.I))
            grava = bool(re.search(GRAVA, corpo, re.I))
            estado = "MORTA" if morta else ("LOGIN" if login else ("GRAVACAO" if grava else
                     ("ABERTA" if campos >= 3 else "SEM FORM")))
            print(f"[{estado:<8}] campos={campos:<3} {titulo}")
            print(f"            {url}")
        except Exception as e:
            print(f"[ERRO    ] {repr(e)[:70]}\n            {url}")
        pg.close()
    ctx.close()
    b.close()
