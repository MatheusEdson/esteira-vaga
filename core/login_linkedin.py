"""Login manual no LinkedIn, uma vez, para a esteira reusar a sessao.

Abre um Edge VISIVEL com perfil persistente. Voce loga na mao (inclusive 2FA).
A senha nunca passa por mim e nao fica salva em lugar nenhum meu: fica no perfil
do browser, igual a quando voce loga normalmente.

  python login_linkedin.py

Rode de novo quando a sessao expirar (a esteira avisa quando isso acontecer).
"""
import os
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py

PERFIL_DIR = os.environ.get(
    "PERFIL_EDGE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "data", "_perfil-edge"))
os.makedirs(PERFIL_DIR, exist_ok=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PERFIL_DIR, channel="msedge", headless=False,
        viewport={"width": 1440, "height": 900}, locale="pt-BR",
        )
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

    print("=" * 74)
    print("Faca o login na janela que abriu. Passe pelo 2FA se pedir.")
    print("Quando o feed do LinkedIn carregar, volte aqui e tecle ENTER.")
    print("=" * 74)
    input()

    pg.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    logado = "feed" in pg.url and "login" not in pg.url
    nome = ""
    try:
        nome = pg.locator("img.global-nav__me-photo").first.get_attribute("alt") or ""
    except Exception:
        pass
    print("\nURL:", pg.url)
    print("SESSAO SALVA:", logado, ("| conta: " + nome) if nome else "")
    print("Perfil persistente em:", PERFIL_DIR)
    if not logado:
        print("\nNAO parece logado. Rode de novo e confirme que o feed carregou antes do ENTER.")
    ctx.close()
