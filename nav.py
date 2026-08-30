"""Camada de navegacao. Todo script de vaga importa daqui.

DOIS MODOS, de proposito:

  `abrir()`            sessao persistente endurecida. Para Upwork e LinkedIn, onde a
                       deteccao decide se voce entra. Recusa headless.
  `sync_playwright`    o lancamento normal do patchright, para formulario de ATS que nao
                       desafia. Reexportado daqui, e nao importado direto do patchright,
                       porque aqui ele ganha chromium_sandbox=True por padrao (ver abaixo).

Nao use `abrir()` para preencher um Greenhouse: sessao persistente e' cara e nao compra
nada onde nao ha desafio. Nao use launch() simples no Upwork: foi exatamente isso que
derrubou a sessao.


MOTIVO. Em 23/08/2026 a Cloudflare desafiou toda navegacao no Upwork e cada tentativa de
"resolver o checkbox" era desfeita pelo relancamento seguinte. A causa nao era a pagina nem
comportamento de mouse: era a identidade do processo. cf_clearance esta amarrado a
fingerprint + IP + UA, e Playwright cru vaza `navigator.webdriver`, rastro de
`Runtime.enable` e bindings injetados na pagina.

Eixos que decidem, em ordem de peso, e o que cada um virou aqui:

  1. IDENTIDADE DO BINARIO -> patchright em vez de playwright. Fork mantido que remove o
     uso de Runtime.enable (principal delator de CDP) e para de injetar bindings.
  2. IDADE DO PERFIL       -> UM perfil, sempre o mesmo, acumulando historico. Diretorio
     recem-criado sem cookie de outro dominio e sinal negativo por si so.
  3. CADENCIA              -> `abrir()` reaproveita; quem precisa de varios passos usa a
     MESMA sessao em vez de relancar.
  4. IP                    -> residencial, nao mexer.
  5. COMPORTAMENTO         -> ultimo lugar. Age depois do load; o desafio e decidido antes.

REGRAS DO PATCHRIGHT que parecem bobas e nao sao (estao na doc dele):
  - persistent context, nunca launch() + new_context()
  - channel real ("msedge"), nunca o chromium empacotado
  - no_viewport=True, porque viewport fixo em janela real e incoerente
  - NAO passar --disable-blink-features=AutomationControlled: o patchright ja resolve, e
    arg custom reintroduz sinal
  - NAO usar add_init_script nem expose_function: sao detectaveis
  - chromium_sandbox=True. O default do Playwright e' False, e isso injeta --no-sandbox
  - headless nunca. Foi headless que derrubou a sessao valida do Upwork.
"""
import os, time

from patchright.sync_api import sync_playwright as _sync_playwright_cru  # noqa: F401
# Reexportado de proposito: os adaptadores fazem `from nav import ErroTempo` para nao
# importar patchright direto e acabar usando o sync_playwright cru, sem o sandbox.
from patchright.sync_api import TimeoutError as ErroTempo  # noqa: F401

# Perfil unico e de longa vida. Trocar para o Edge pessoal (mais confianca, blast radius
# maior) e' so' apontar VAGAS_PERFIL para o user-data-dir dele.
PERFIL = os.environ.get(
    "VAGAS_PERFIL",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "_perfil-nav"))

CANAL = os.environ.get("VAGAS_CANAL", "msedge")

# pyflakes nao honra `# noqa` (isso e do flake8), e o CI roda pyflakes. __all__ e' o que ele
# entende como reexport deliberado. Serve de documentacao tambem: e' a superficie publica.
__all__ = ["sync_playwright", "ErroTempo", "abrir", "aba", "bloqueado",
           "esperar_humano", "submissao_ok", "PERFIL", "CANAL"]

# ---------------------------------------------------------------------------------
# O sandbox vale nos DOIS modos, e por isso e' aplicado aqui e nao so' em abrir().
#
# O Playwright passa chromium_sandbox=False por padrao, o que injeta --no-sandbox, e o
# Chromium responde com a tarja "sinalizador sem suporte". Navegador de pessoa nunca roda
# assim: e' sinal de automacao visivel ate' a olho nu, e entra no fingerprint.
#
# Antes disto, o endurecimento morava em abrir(), que nao tinha nenhum caller. Os 22
# arquivos importavam `sync_playwright` e lancavam na mao, entao a politica nao alcancava
# nenhuma linha que rodava de verdade. Envolvendo no ponto que todos ja' usam, alcanca.
#
# Quem precisar do default do Playwright passa chromium_sandbox=False explicitamente.
_SANDBOX = os.environ.get("VAGAS_SANDBOX", "1") != "0"


class _ChromiumComSandbox:
    def __init__(self, real):
        self._real = real

    def __getattr__(self, nome):
        return getattr(self._real, nome)

    def launch(self, **kw):
        kw.setdefault("chromium_sandbox", _SANDBOX)
        return self._real.launch(**kw)

    def launch_persistent_context(self, **kw):
        kw.setdefault("chromium_sandbox", _SANDBOX)
        return self._real.launch_persistent_context(**kw)


class _PlayComSandbox:
    def __init__(self, real):
        self._real = real

    def __getattr__(self, nome):
        return getattr(self._real, nome)

    @property
    def chromium(self):
        return _ChromiumComSandbox(self._real.chromium)


class _CtxSandbox:
    """Mesma API de `with sync_playwright() as p`, so' que `p.chromium` vem envolvido."""

    def __init__(self, ctx):
        self._ctx = ctx

    def __enter__(self):
        return _PlayComSandbox(self._ctx.__enter__())

    def __exit__(self, *a):
        return self._ctx.__exit__(*a)

    def start(self):
        return _PlayComSandbox(self._ctx.start())


def sync_playwright():
    """Igual ao do patchright, com chromium_sandbox=True por padrao."""
    return _CtxSandbox(_sync_playwright_cru())



def abrir(play, perfil=None, headless=False, locale="en-US", tz="America/Sao_Paulo",
          baixar_em=None):
    """Contexto persistente endurecido. Nao passa arg custom de proposito."""
    caminho = perfil or PERFIL
    os.makedirs(caminho, exist_ok=True)
    if headless:
        # deixo explodir em vez de silenciosamente virar detectavel
        raise ValueError("headless nao: foi o que derrubou a sessao do Upwork. Use janela.")
    kw = dict(
        user_data_dir=caminho,
        channel=CANAL,
        headless=False,
        no_viewport=True,
        locale=locale,
        timezone_id=tz,
        # O Playwright desliga o sandbox por PADRAO, o que injeta --no-sandbox e faz o
        # Chromium mostrar a tarja "sinalizador sem suporte". Navegador de humano nunca
        # roda assim: e' sinal de automacao visivel ate' a olho nu, e passa no fingerprint.
        chromium_sandbox=True,
    )
    if baixar_em:
        os.makedirs(baixar_em, exist_ok=True)
        kw["accept_downloads"] = True
        kw["downloads_path"] = baixar_em
    ctx = play.chromium.launch_persistent_context(**kw)
    return ctx


def aba(ctx, preferir=None):
    """Devolve a aba util. Varre TODAS: link que abre em aba nova deixava pages[0] parada
    na URL antiga, e foi assim que um leitor jurou que o login nao tinha acontecido."""
    abas = list(ctx.pages)
    if not abas:
        return ctx.new_page()
    if preferir:
        for a in abas:
            try:
                if preferir in a.url:
                    return a
            except Exception:
                continue
    return abas[-1]


def bloqueado(pg):
    """True se a pagina e' interstitial de bot check, nao a pagina real."""
    try:
        t = (pg.title() or "").lower()
    except Exception:
        return False
    return any(s in t for s in ("just a moment", "verify you are human",
                                "attention required", "checking your browser"))


def esperar_humano(pg, rotulo="", espera=900):
    """Para e espera o humano resolver. Nao tenta contornar.

    Um clique grava cf_clearance e libera a sessao inteira, desde que ninguem relance o
    browser depois. E' por isso que esta funcao existe em vez de um retry."""
    if not bloqueado(pg):
        return True
    print("\n  !! bot check em %s" % (rotulo or pg.url[:70]), flush=True)
    print("     CLIQUE no checkbox da janela. Espero %d min." % (espera // 60), flush=True)
    try:
        pg.bring_to_front()
    except Exception:
        pass
    limite = time.time() + espera
    while time.time() < limite:
        time.sleep(4)
        if not bloqueado(pg):
            print("     liberado, seguindo", flush=True)
            time.sleep(3)
            return True
    print("     nao liberado em %ds" % espera, flush=True)
    return False


def submissao_ok(respostas):
    """Prova de envio e' POST com 2xx. Nada mais conta.

    Texto de sucesso na tela mente, endpoint de telemetria devolve 201 com form vazio, e
    ja tive detector meu jurando ENVIOU so' porque existia um POST."""
    for r in respostas:
        try:
            if r.request.method == "POST" and 200 <= r.status < 300:
                return True, "%s %d" % (r.url[:90], r.status)
        except Exception:
            continue
    return False, "nenhum POST 2xx"
