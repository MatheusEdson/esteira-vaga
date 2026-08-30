"""Abre um browser VISIVEL com perfil persistente para voce fazer o passo manual
(login, Continue with Google, captcha "verify you are human"). Depois disso a esteira
reusa a sessao salva e segue sozinha.

  python abrir_sessao.py near      https://jobs.hirewithnear.com/jobs/2708
  python abrir_sessao.py linkedin  https://www.linkedin.com/login

Sua senha nunca passa por mim: fica no perfil do browser, igual a um login normal.
"""
import sys, os
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py

BASE = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) < 3:
    raise SystemExit(__doc__)
nome, url = sys.argv[1], sys.argv[2]
perfil = os.path.join(BASE, "_tmp", f"edge-profile-{nome}")
os.makedirs(perfil, exist_ok=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        perfil, channel="msedge", headless=False,
        viewport={"width": 1440, "height": 950}, locale="pt-BR",
        )
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.goto(url, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(3000)

    # Credenciais vem de variavel de ambiente, nunca de arquivo. Se nao existirem,
    # o script so abre o browser e voce digita.
    usuario = os.environ.get("VAGAS_LOGIN", "")
    senha = os.environ.get("VAGAS_SENHA", "")
    if usuario and senha:
        preenchidos = 0
        for sel in ["input[name='session_key']", "input[name='identifier']",
                    "input[name='emailAddress']", "input[type='email']"]:
            try:
                el = pg.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.fill(usuario); preenchidos += 1; break
            except Exception:
                pass
        for sel in ["input[name='session_password']", "input[name='password']",
                    "input[type='password']"]:
            try:
                el = pg.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.fill(senha); preenchidos += 1; break
            except Exception:
                pass
        print(f"Campos de login preenchidos: {preenchidos} (a senha nao e' gravada em disco)")
    else:
        print("Sem VAGAS_LOGIN/VAGAS_SENHA no ambiente: digite na janela.")

    print("=" * 76)
    print(f"Perfil: {perfil}")
    print("Faca o passo manual na janela que abriu (login, Google, captcha).")
    print("Quando terminar e estiver logado, volte aqui e tecle ENTER.")
    print("=" * 76)
    input()

    pg.wait_for_timeout(1500)
    print("\nURL atual:", pg.url)
    cookies = ctx.cookies()
    print(f"Cookies salvos no perfil: {len(cookies)}")
    corpo = pg.inner_text("body").lower()
    if "log in" in corpo and "log out" not in corpo:
        print("AVISO: a pagina ainda mostra 'Log in'. Confirme que o login concluiu.")
    else:
        print("Sessao aparentemente ativa.")
    ctx.close()
