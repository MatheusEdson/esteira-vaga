"""PetPrinted · Senior Performance Marketing Manager (Meta) · form proprio.

  python aplicar_petprinted.py --video <URL>            # dry-run
  python aplicar_petprinted.py --video <URL> --submit   # envia
  python aplicar_petprinted.py --video <URL> --janela   # abre preenchido para ele conferir

A vaga: print-on-demand de produtos de pet, 9 lojas Shopify (Europa, America do Norte,
Australia). "Remote (worldwide)", "Fluent English", sem alemao.
As respostas longas e os numeros de negociacao (pretensao, verba gerida, anos de
experiencia) vem do data/perfil.json, que fica fora do git. Este arquivo guarda so
a mecanica do formulario.
"""
import sys, os, re, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.bootstrap import ID, do_perfil, bloco, tmp, sync_playwright




URL = "https://jobs.petprinted.de/jobs/senior-performance-marketing-meta"
SUBMIT = "--submit" in sys.argv
JANELA = "--janela" in sys.argv
if "--video" not in sys.argv:
    raise SystemExit("ERRO: o campo do screen-share e OBRIGATORIO.\n"
                     "  python aplicar_petprinted.py --video https://www.loom.com/share/...")
VIDEO = sys.argv[sys.argv.index("--video") + 1]

# ordem das perguntas confirmada no recon de 20/08
NOME       = ID["nome_completo"]
EMAIL      = ID["email"]
PAIS       = "Brazil"
FUSO       = "GMT-3"
INICIO     = "2026-09-01"      # data no formato do input type=date
TAXA       = do_perfil("expected_salary_usd_month")   # monthly rate USD
FREELANCER = "Individual freelancer"
EXCLUSIVO  = "Yes, full time and exclusive from the start"
ANOS_ECOM  = "3 to 5 years"
ANOS_META  = "3 to 5 years"
VERBA_META = "25,000 to 100,000 USD"
HORARIO    = ("GMT-3 (Brazil). I work 09:00 to 18:00 local, which overlaps European "
              "afternoons and US mornings, and I can shift earlier to cover full CET hours.")
ORIGEM     = "Facebook / Instagram"

PORTFOLIO = bloco("PORTFOLIO")


def sel_por_texto(pg, indice, texto):
    """Seleciona opcao por TEXTO no n-esimo <select> da pagina."""
    return pg.evaluate("""([i, txt]) => {
        const ss = [...document.querySelectorAll('select')];
        const s = ss[i];
        if (!s) return 'select ausente';
        const o = [...s.options].find(x => x.text.trim() === txt);
        if (!o) return 'opcao ausente: ' + [...s.options].map(x=>x.text.trim()).slice(0,6).join(' / ');
        s.value = o.value;
        s.dispatchEvent(new Event('input',  {bubbles: true}));
        s.dispatchEvent(new Event('change', {bubbles: true}));
        return s.options[s.selectedIndex].text.trim(); }""", [indice, texto])


with sync_playwright() as p:
    b = p.chromium.launch(headless=not JANELA, channel="msedge",
                          )
    ctx = b.new_context(viewport={"width": 1400, "height": 1400}, locale="en-US")
    pg = ctx.new_page()

    rede = []
    pg.on("request", lambda r: rede.append(("REQ", r.method, r.url[:120]))
          if r.method in ("POST", "PUT") else None)
    pg.on("response", lambda r: rede.append(("RES", str(r.status), r.url[:120]))
          if r.request.method in ("POST", "PUT") else None)

    print("[1]", URL)
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(9000)
    for _ in range(6):
        pg.mouse.wheel(0, 3000)
        pg.wait_for_timeout(600)

    # GOTCHA: NAO usar indice dentro de um tipo (input[type=text] etc). Os inputs de data e
    # numero contam como text em momentos diferentes da hidratacao, entao o indice MUDA entre
    # um passo e outro: o nome caiu no campo de horario. A lista UNIFICADA em ordem de DOM e
    # estavel. Ordem confirmada no recon de 20/08.
    PLANO = [
        (0,  "nome",       NOME),
        (1,  "email",      EMAIL),
        (2,  "pais",       PAIS),
        (3,  "fuso",       FUSO),
        (4,  "inicio",     INICIO),
        (5,  "taxa",       TAXA),
        (6,  "freelancer", FREELANCER),
        (7,  "exclusivo",  EXCLUSIVO),
        (8,  "anos ecom",  ANOS_ECOM),
        (9,  "anos meta",  ANOS_META),
        (10, "verba meta", VERBA_META),
        (11, "horario",    HORARIO),
        (12, "portfolio",  PORTFOLIO),
        (13, "video",      VIDEO),
        (14, "origem",     ORIGEM),
    ]
    # :visible e obrigatorio aqui: existe um input INVISIVEL antes do campo de video, e sem
    # o filtro a lista desloca um no fim (o valor do "origem" acabava dentro do campo de URL).
    controles = pg.locator("input:not([type=hidden]):not([type=checkbox]):visible, "
                           "textarea:visible, select:visible")
    print("[2] preenchendo por posicao na lista unificada (%d controles)" % controles.count())
    for i, rotulo, valor in PLANO:
        try:
            el = controles.nth(i)
            tag = el.evaluate("e => e.tagName")
            if tag == "SELECT":
                r = el.evaluate("""(s, txt) => {
                    const o = [...s.options].find(x => x.text.trim() === txt);
                    if (!o) return 'opcao ausente: ' +
                        [...s.options].map(x => x.text.trim()).slice(0, 5).join(' / ');
                    s.value = o.value;
                    s.dispatchEvent(new Event('input',  {bubbles: true}));
                    s.dispatchEvent(new Event('change', {bubbles: true}));
                    return s.options[s.selectedIndex].text.trim(); }""", valor)
                print("   [%2d] %-12s %s" % (i, rotulo, r))
            else:
                el.fill(valor)
                lido = el.input_value()
                marca = "" if lido.strip()[:30] == valor.strip()[:30] else "  <-- DIVERGIU"
                print("   [%2d] %-12s %s%s" % (i, rotulo, lido[:52], marca))
        except Exception as ex:
            print("   [%2d] %-12s FALHOU %s" % (i, rotulo, str(ex)[:60]))

    print("[5] consentimento (NAO e checkbox: e elemento clicavel)")
    r = pg.evaluate("""() => {
        const alvo = [...document.querySelectorAll('button,label,div,span,input')]
          .find(e => /I consent to Pet Printed/i.test(e.innerText || e.textContent || ''));
        if (!alvo) return 'nao encontrado';
        const cb = alvo.querySelector ? alvo.querySelector('input[type=checkbox]') : null;
        if (cb) { if (!cb.checked) cb.click(); return 'checkbox interno = ' + cb.checked; }
        alvo.click();
        const depois = alvo.getAttribute('aria-checked') || alvo.getAttribute('data-state') || 'clicado';
        return 'clicado, estado=' + depois; }""")
    print("   consentimento:", r)

    print("\n[6] ESTADO FINAL")
    for l in pg.evaluate("""() => {
          const vis = e => { const r = e.getBoundingClientRect(); return r.width>0 && r.height>0; };
          const out = [];
          document.querySelectorAll('input,textarea,select').forEach(e => {
            if (['hidden','submit','button','image'].includes(e.type)) return;
            if (e.type === 'checkbox') { out.push('consent = ' + (e.checked ? 'MARCADO' : 'VAZIO')); return; }
            if (!vis(e)) return;
            let v = e.value || '';
            if (e.tagName === 'SELECT') v = e.options[e.selectedIndex] ? e.options[e.selectedIndex].text : '';
            out.push((e.name || e.id || e.type || e.tagName) + ' = ' + String(v).slice(0, 72));
          });
          return out; }"""):
        print("   ", l)

    vazios = pg.evaluate("""() => [...document.querySelectorAll('input,textarea,select')]
          .filter(e => !['hidden','submit','button','image','checkbox'].includes(e.type))
          .filter(e => { const r = e.getBoundingClientRect(); return r.width>0 && r.height>0; })
          .filter(e => !(e.value||'').trim() ||
                       (e.tagName==='SELECT' && /^select/i.test(e.options[e.selectedIndex].text)))
          .map(e => e.type || e.tagName)""")
    print("\n   campos ainda vazios:", vazios or "nenhum")

    pg.screenshot(path=tmp("petprinted-preenchido.png"), full_page=True)

    if JANELA:
        print("\nJANELA ABERTA. Confira e clique em Submit application.")
        while len(ctx.pages) > 0:
            time.sleep(5)
    elif SUBMIT:
        if vazios:
            print("\n[7] ABORTADO: ainda ha campo obrigatorio vazio.")
        else:
            print("\n[7] ENVIANDO")
            try:
                bt = pg.locator("button:has-text('Submit application')").first
                bt.scroll_into_view_if_needed()
                pg.wait_for_timeout(900)
                bt.click()
            except Exception as ex:
                print("   erro no clique:", str(ex)[:90])
            for i in range(14):
                pg.wait_for_timeout(3000)
                corpo = pg.inner_text("body")
                ok = re.search(r"thank you|thanks|submitted|received|success", corpo, re.I)
                err = [l.strip() for l in corpo.split("\n")
                       if re.search(r"required|invalid|error", l, re.I) and len(l.strip()) < 110]
                print(f"   t={3*(i+1):>2}s sucesso={bool(ok)} erros={err[:2]}")
                if ok:
                    break
            print("   URL final:", pg.url[:110])
            print("\n   --- rede: a PROVA e um POST de submissao com 2xx ---")
            for t in rede:
                if not any(x in t[2] for x in ("google", "facebook", "sentry", "hotjar")):
                    print("   ", t)
            pg.screenshot(path=tmp("petprinted-enviado.png"), full_page=True)
    else:
        print("\n[7] DRY-RUN: nada enviado.")

    ctx.close()
    b.close()
