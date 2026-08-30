"""Hire With Near: cria conta (autorizado pelo Matheus) e segue o fluxo de candidatura.

  python aplicar_near.py            -> anda o fluxo e dumpa, sem enviar candidatura
  python aplicar_near.py --submit   -> vai ate o fim

A senha vem da variavel de ambiente NEAR_SENHA. Nunca fica no codigo, nunca no git
de nenhuma outra conta dele.
"""
import sys, os
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py

BASE = os.path.dirname(os.path.abspath(__file__))
from core.perfil import perfil as _carregar_perfil   # le data/perfil.json
PERFIL = _carregar_perfil()
from core.perfil import curriculo as _cv
ID = PERFIL["identidade"]
CV = _cv("web_seo")
URL = "https://jobs.hirewithnear.com/jobs/2708?src=brenda.lindenberg"
SENHA = os.environ.get("NEAR_SENHA", "")  # nunca hardcoded: veja .env.example
DO_SUBMIT = "--submit" in sys.argv

CAMPOS = """() => [...document.querySelectorAll('input, textarea, select')]
  .filter(e => !['hidden','submit'].includes(e.type) && e.offsetParent !== null)
  .map(e => ({type: e.type, name: e.name||'', ph: e.placeholder||'', req: e.required,
              val: e.type==='file' ? (e.files&&e.files.length?e.files[0].name:'') : (e.value||'').slice(0,50)}))"""


def dump(pg, tag):
    print(f"\n--- {tag} ---")
    print("  URL:", pg.url)
    for c in pg.evaluate(CAMPOS):
        print(f"   {c['type']:<10} name={c['name']:<26} ph={c['ph'][:34]:<34} req={c['req']} val={c['val'][:40]}")
    btns = pg.evaluate("""() => [...document.querySelectorAll('button, input[type=submit]')]
        .filter(e => e.offsetParent !== null).map(e => (e.innerText||e.value||'').trim().slice(0,40)).filter(t=>t)""")
    print("   botoes:", btns[:14])


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        os.path.join(BASE, "_tmp", "edge-profile-near"), channel="msedge", headless=True,
        viewport={"width": 1440, "height": 1100}, locale="en-US",
        accept_downloads=True)
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()

    print("[1] abrindo vaga")
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(4000)

    print("[2] Apply Now")
    pg.locator("button:has-text('Apply Now'), a:has-text('Apply Now')").first.click(timeout=20000)
    pg.wait_for_timeout(4000)

    # ja logado? entao o form de auth nao aparece
    tem_auth = pg.locator("input[name='identifier'], input[name='emailAddress']").count() > 0
    if tem_auth:
        print("[3] criando conta")
        try:
            pg.locator("a:has-text('Sign up')").first.click(timeout=8000)
            pg.wait_for_timeout(3000)
        except Exception:
            print("   ja estava na tela de cadastro")
        pg.fill("input[name='firstName']", ID["first_name"])
        pg.fill("input[name='lastName']", ID["last_name"])
        pg.fill("input[name='emailAddress']", ID["email"])
        pg.fill("input[name='password']", SENHA)
        dump(pg, "cadastro preenchido")
        pg.locator("button:has-text('Continue')").first.click(timeout=15000)
        pg.wait_for_timeout(9000)
        dump(pg, "depois do Continue")
    else:
        print("[3] sessao ja existente, pulando cadastro")
        dump(pg, "estado atual")

    # tenta seguir o fluxo de candidatura
    for passo in range(1, 7):
        campos = pg.evaluate(CAMPOS)
        # anexa CV se houver campo de arquivo vazio
        for i, c in enumerate(campos):
            if c["type"] == "file" and not c["val"]:
                try:
                    pg.locator("input[type=file]").nth(i).set_input_files(CV)
                    print(f"   anexou CV no campo {c['name']}")
                    pg.wait_for_timeout(4000)
                except Exception as e:
                    print("   anexo falhou:", repr(e)[:70])
        avancou = False
        for sel in ["button:has-text('Submit application')", "button:has-text('Submit')",
                    "button:has-text('Apply')", "button:has-text('Continue')",
                    "button:has-text('Next')"]:
            try:
                bt = pg.locator(sel).first
                if bt.is_visible(timeout=2000) and not bt.is_disabled():
                    rotulo = bt.inner_text().strip()
                    if not DO_SUBMIT and any(w in rotulo.lower() for w in ("submit", "apply")):
                        print(f"\n[PAUSA] botao final '{rotulo}' encontrado. DRY-RUN, nao cliquei.")
                        dump(pg, "estado final do dry-run")
                        pg.screenshot(path=os.path.join(BASE, "_tmp", "near-final.png"), full_page=True)
                        ctx.close(); raise SystemExit(0)
                    print(f"[4.{passo}] clicando '{rotulo}'")
                    bt.click()
                    pg.wait_for_timeout(7000)
                    dump(pg, f"apos '{rotulo}'")
                    avancou = True
                    break
            except SystemExit:
                raise
            except Exception:
                pass
        if not avancou:
            print(f"\n[fim] nada mais para clicar no passo {passo}")
            break

    dump(pg, "ESTADO FINAL")
    pg.screenshot(path=os.path.join(BASE, "_tmp", "near-final.png"), full_page=True)
    corpo = pg.inner_text("body").lower()
    for marca in ("application submitted", "thank you", "we received", "successfully applied",
                  "verify your email", "confirm your email"):
        if marca in corpo:
            print(f">>> SINAL: '{marca}'")
    ctx.close()
