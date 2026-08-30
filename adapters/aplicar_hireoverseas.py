"""Hire Overseas · Performance Marketing Manager (Workable em dominio proprio).

  python aplicar_hireoverseas.py [--submit]

Respostas de plataforma: Amazon PPC e Walmart e TikTok = NAO (ele nao tem).
Meta e Google = SIM. Contribution margin/TACOS = "Somewhat" (TACOS e' jargao de Amazon).
"""
import sys, os, json, re, time
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py

JANELA = "--janela" in sys.argv   # abre visivel e deixa o Matheus resolver o Turnstile

BASE = os.path.dirname(os.path.abspath(__file__))
from core.perfil import perfil as _carregar_perfil   # le data/perfil.json
PERFIL = _carregar_perfil()
from core.perfil import curriculo as _cv, anexo as _anexo, respostas_md as _resp
ID = PERFIL["identidade"]

def do_perfil(chave, secao="respostas_padrao"):
    """Le do perfil e ABORTA se estiver vazio.

    Existe porque estes adaptadores nasceram como script de uma candidatura so', com o
    valor real digitado inline: pretensao, ultimo salario, empregador atual. Isso publica
    a posicao de negociacao de quem usa o repo e trava o adaptador em uma pessoa so'.
    Vazio aborta de proposito: melhor parar do que mandar numero errado."""
    v = PERFIL.get(secao, {}).get(chave)
    v = str(v).strip() if v is not None else ""
    if not v:
        raise SystemExit("ERRO: preencha %s.%s no data/perfil.json" % (secao, chave))
    return v

AN = PERFIL["anexos"]
CV = _cv("paid_seo")
PORTFOLIO = _anexo("portfolio_pdf")
URL = "https://careers.hireoverseas.com/_/j/68E7F0BB61/apply/"
DO_SUBMIT = "--submit" in sys.argv

TEXTOS = {
    "firstname": ID["first_name"],
    "lastname": ID["last_name"],
    "email": ID["email"],
    "phone": ID.get("telefone_e164", "").lstrip("+"),
    "address": "%s, %s, %s" % (ID["cidade"], ID["estado"], ID["pais"]),
    "CA_49049": AN["loom_intro"],                  # link do Loom
    "CA_40664": ID["linkedin_url"],
    "CA_44927": "55TELEFONE_DO_PERFIL",                   # WhatsApp
    "CA_47793": ID["email"],
    "CA_39656": do_perfil("expected_salary_usd_month"),   # salary USD
    "CA_41260": "Within 2 weeks",                  # how soon can you start
}

RADIOS = {
    "CA_42208": "418955",        # onde ouviu falar = LinkedIn
    "CA_40313": "392318",        # fuso EUA = Yes
    "CA_43109": "438468",        # time-tracking = Yes
    "QA_12256556": "false",      # Amazon PPC = NO
    "QA_12256557": "false",      # Walmart Connect = NO
    "QA_12256558": "true",       # Meta Ads = YES
    "QA_12256559": "true",       # Google Ads = YES
    "QA_12256560": "false",      # TikTok = NO
    "QA_12256562": "true",       # full-time US hours = YES
    "QA_12256563": "true",       # reconhece exigencia do Loom = YES
}

with sync_playwright() as p:
    b = p.chromium.launch(headless=not JANELA, channel="msedge",
                          )
    ctx = b.new_context(viewport={"width": 1400, "height": 1100}, locale="pt-BR")
    pg = ctx.new_page()
    print("[1]", URL)
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(6000)

    # cookies + backdrop: no Workable o backdrop engole o clique no submit
    for sel in ["button:has-text('Accept all')", "button:has-text('Accept')"]:
        try:
            bt = pg.locator(sel).first
            if bt.is_visible(timeout=2500):
                bt.click(); pg.wait_for_timeout(1200); break
        except Exception:
            pass
    sobrou = pg.evaluate("""() => { const bs = [...document.querySelectorAll('[data-ui="backdrop"]')];
                                    bs.forEach(x => x.remove()); return bs.length; }""")
    print(f"   backdrops removidos: {sobrou}")

    print("[2] textos")
    for nome, valor in TEXTOS.items():
        ok = False
        for sel in (f"input[name='{nome}']", f"textarea[name='{nome}']"):
            try:
                el = pg.locator(sel).first
                el.wait_for(state="visible", timeout=5000)
                el.fill(valor)
                ok = True
                break
            except Exception:
                continue
        print(f"   {nome:<12} {'ok' if ok else 'NAO PREENCHIDO'}  {valor[:46]}")

    print("[3] radios")
    for nome, valor in RADIOS.items():
        r = pg.evaluate("""([n, v]) => { const e = document.querySelector(
              `input[type=radio][name="${n}"][value="${v}"]`);
            if (!e) return 'ausente'; if (!e.checked) e.click(); return e.checked; }""", [nome, valor])
        print(f"   {nome:<13} = {valor:<6} {r}")

    print("[4] contribution margin / TACOS (clique pelo texto)")
    alvo = "Somewhat, I am familiar with these metrics but primarily optimize for ROAS"
    r = pg.evaluate("""(txt) => {
        const el = [...document.querySelectorAll('label, span, div')]
          .find(e => e.children.length === 0 && e.innerText && e.innerText.trim().startsWith(txt.slice(0, 40)));
        if (!el) return 'opcao nao achada';
        el.click(); return 'clicado';
      }""", alvo)
    print("   ", r)

    print("[5] arquivos")
    finputs = pg.locator("input[type=file]")
    n = finputs.count()
    print("   file inputs:", n)
    if n >= 1:
        finputs.nth(0).set_input_files(CV)
        print("   slot 0 = CV", os.path.basename(CV))
    if n >= 2:
        finputs.nth(1).set_input_files(PORTFOLIO)
        print("   slot 1 = portfolio", os.path.basename(PORTFOLIO))
    for i in range(12):
        pg.wait_for_timeout(2000)
        vistos = pg.evaluate("""() => [...document.querySelectorAll('*')]
              .filter(e => e.children.length === 0 && /\\.pdf$/i.test((e.innerText||'').trim()))
              .map(e => e.innerText.trim())""")
        if len(set(vistos)) >= min(n, 2):
            print(f"   arquivos confirmados em {2*(i+1)}s: {sorted(set(vistos))}")
            break

    print("\n[6] VERIFICACAO")
    faltando = []
    for nome in TEXTOS:
        lido = pg.evaluate("""(n) => { const e = document.querySelector(`[name="${n}"]`);
                                       return e ? (e.value || '') : '(ausente)'; }""", nome)
        if not lido.strip():
            faltando.append(nome)
    for nome in RADIOS:
        m = pg.evaluate("""(n) => !!document.querySelector(`input[name="${n}"]:checked`)""", nome)
        if not m:
            faltando.append(nome)
    print("   vazios:", faltando if faltando else "nenhum")

    pg.screenshot(path=os.path.join(BASE, "_tmp", "ho-preenchido.png"), full_page=True)

    if JANELA:
        print("\n" + "=" * 76)
        print("JANELA ABERTA E PREENCHIDA.")
        print("Falta so' voce: marcar 'Confirme que e' humano' (Cloudflare) e clicar")
        print("em 'Submit application'. Nao feche antes, o preenchimento vive nesta janela.")
        print("=" * 76)
        while len(ctx.pages) > 0:
            time.sleep(5)
    elif DO_SUBMIT and faltando:
        print("\n[7] ABORTADO: campos vazios acima.")
    elif DO_SUBMIT:
        print("\n[7] ENVIANDO")
        for sel in ["button:has-text('Accept all')"]:
            try:
                bt = pg.locator(sel).first
                if bt.is_visible(timeout=2000):
                    bt.click(); pg.wait_for_timeout(1000)
            except Exception:
                pass
        pg.evaluate("""() => document.querySelectorAll('[data-ui="backdrop"]').forEach(x => x.remove())""")
        bt = pg.locator("button:has-text('Submit application')").first
        bt.scroll_into_view_if_needed()
        pg.wait_for_timeout(1200)
        bt.click()
        for i in range(14):
            pg.wait_for_timeout(3000)
            corpo = pg.inner_text("body")
            ok = re.search(r"thank you|application (was )?(submitted|received)|we.ve received", corpo, re.I)
            erro = [l.strip() for l in corpo.split("\n")
                    if re.search(r"is required|please (fill|enter|select)|invalid", l, re.I)]
            print(f"   t={3*(i+1):>2}s sucesso={bool(ok)} erros={erro[:2]}")
            if ok:
                break
        print("   URL:", pg.url)
        pg.screenshot(path=os.path.join(BASE, "_tmp", "ho-enviado.png"), full_page=True)
    else:
        print("\n[7] DRY-RUN: nada enviado.")

    ctx.close()
    b.close()
