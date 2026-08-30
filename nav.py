"""Camada de navegacao endurecida. Todo script de vaga entra por aqui.

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

from patchright.sync_api import sync_playwright, TimeoutError as ErroTempo  # noqa: F401

# Perfil unico e de longa vida. Trocar para o Edge pessoal (mais confianca, blast radius
# maior) e' so' apontar VAGAS_PERFIL para o user-data-dir dele.
PERFIL = os.environ.get(
    "VAGAS_PERFIL",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "_perfil-nav"))

CANAL = os.environ.get("VAGAS_CANAL", "msedge")


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
