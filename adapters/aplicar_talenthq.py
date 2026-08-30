"""TalentHQ · Paid Media Account Executive (careers-page.com).

  python aplicar_talenthq.py            # dry-run
  python aplicar_talenthq.py --submit    # envia

Notas de decisao:
  - "Why should we consider YOU for this position?" = PLATANO, literal. A vaga pede isso de
    proposito, e o campo e input de UMA linha, o que confirma que esperam so a palavra.
    E filtro de atencao: quem escreve paragrafo falhou no teste.
  - Resume em INGLES obrigatorio ("Only Resumes in English will be considered").
  - Gender = "Prefer Not to Say": campo de diversidade, nao qualificacao. Nao presumo.
  - NAO afirmar LinkedIn Ads (esta no NUNCA_AFIRMAR). O requisito da vaga e OR entre
    Google / Meta / LinkedIn / Programmatic, e Google + Meta ja satisfaz.
"""
import sys, os, json, re, time
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py

BASE = os.path.dirname(os.path.abspath(__file__))
PERFIL = json.load(open(os.path.join(BASE, "perfil.json"), encoding="utf-8"))
ID = PERFIL["identidade"]
CV = os.path.join(BASE, PERFIL["curriculos"]["paid_seo"])

URL = "https://www.careers-page.com/talenthq/job/7XV78493"
SUBMIT = "--submit" in sys.argv
JANELA = "--janela" in sys.argv

CAMPOS = {
    "1530182": ID["nome_completo"],                # Full Name
    "1530183": ID["email"],                        # Email
    "1530184": ID["telefone_formatado"],           # Phone
    "1530188": "Brazil",                           # Country of Residence
    "1530189": "PLATANO",                          # Why should we consider YOU
}
GENERO = "Prefer Not to Say"

if not os.path.exists(CV):
    raise SystemExit("ERRO: nao achei " + CV)

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
    pg.wait_for_timeout(8000)

    print("[2] abrindo o formulario")
    for sel in ("button.btn-lg", "a:has-text('Apply')", "button:has-text('Apply')"):
        try:
            el = pg.locator(sel).last
            if el.is_visible(timeout=2500):
                el.scroll_into_view_if_needed()
                pg.wait_for_timeout(500)
                el.click()
                print("   cliquei:", sel)
                break
        except Exception:
            continue
    pg.wait_for_timeout(8000)
    print("   URL:", pg.url)

    print("[3] campos de texto")
    for nome, valor in CAMPOS.items():
        ok = False
        for sel in (f"input[name='{nome}']", f"#{nome}", f"textarea[name='{nome}']"):
            try:
                el = pg.locator(sel).first
                el.wait_for(state="visible", timeout=4000)
                el.fill(valor)
                ok = True
                break
            except Exception:
                continue
        print(f"   {nome} {'ok':<4} {valor[:52]}" if ok else f"   {nome} FALHOU  {valor[:52]}")

    print("[4] genero (widget de select com busca)")
    feito = False
    try:
        # select nativo por tras do widget
        r = pg.evaluate("""(v) => {
            const s = document.querySelector("select[name='1653666'], #1653666");
            if (!s) return 'sem select';
            const o = [...s.options].find(x => x.text.trim() === v);
            if (!o) return 'opcao ausente';
            o.selected = true;
            s.dispatchEvent(new Event('change', {bubbles: true}));
            return s.value; }""", GENERO)
        print("   via select nativo:", r)
        feito = r not in ("sem select", "opcao ausente")
    except Exception as ex:
        print("   erro select:", str(ex)[:90])
    if not feito:
        try:
            pg.locator("input[type=search]").first.click()
            pg.wait_for_timeout(600)
            pg.keyboard.type(GENERO, delay=90)
            pg.wait_for_timeout(1200)
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(800)
            print("   via widget de busca: ok")
        except Exception as ex:
            print("   erro widget:", str(ex)[:90])

    print("[5] curriculo (ingles)")
    try:
        pg.locator("input[type=file]").first.set_input_files(CV)
        pg.wait_for_timeout(3000)
        print("   anexado:", os.path.basename(CV))
    except Exception as ex:
        print("   FALHOU:", str(ex)[:110])

    print("[6] termos")
    r = pg.evaluate("""() => {
        const c = document.querySelector("input[name='terms_and_condition']");
        if (!c) return 'ausente';
        if (!c.checked) c.click();
        return c.checked; }""")
    print("   terms_and_condition =", r)

    print("\n[7] ESTADO FINAL")
    for l in pg.evaluate("""() => {
          const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
          const out = [];
          document.querySelectorAll('input,textarea,select').forEach(e => {
            if (['hidden','submit','button','image'].includes(e.type)) return;
            if (e.type !== 'checkbox' && !vis(e)) return;
            let v = e.value || '';
            if (e.type === 'checkbox') v = e.checked ? 'MARCADO' : 'vazio';
            if (e.tagName === 'SELECT') v = [...e.selectedOptions].map(o => o.text).join(',');
            if (e.type === 'file') v = e.files && e.files.length ? e.files[0].name : '(sem arquivo)';
            out.push((e.name || e.id || e.tagName) + ' = ' + String(v).slice(0, 70));
          });
          return out; }"""):
        print("   ", l)

    if JANELA:
        print("\nJANELA ABERTA. Confira e envie.")
        while len(ctx.pages) > 0:
            time.sleep(5)
    elif SUBMIT:
        print("\n[8] ENVIANDO")
        clic = False
        for sel in ("button[type=submit]", "input[type=submit]", "button:has-text('Submit')",
                    "button:has-text('Apply')", ".btn-success"):
            try:
                bt = pg.locator(sel).last
                if bt.is_visible(timeout=2500):
                    bt.scroll_into_view_if_needed()
                    pg.wait_for_timeout(800)
                    print("   botao:", sel, "|", (bt.inner_text() or "").strip()[:40])
                    bt.click()
                    clic = True
                    break
            except Exception:
                continue
        if not clic:
            print("   NENHUM BOTAO DE ENVIO ENCONTRADO")
        for i in range(12):
            pg.wait_for_timeout(3000)
            corpo = pg.inner_text("body")
            ok = re.search(r"thank you|thanks|submitted|received|success|application sent", corpo, re.I)
            err = [l.strip() for l in corpo.split("\n")
                   if re.search(r"is required|required field|please (fill|enter|select)|invalid", l, re.I)
                   and len(l.strip()) < 120]
            print(f"   t={3*(i+1):>2}s sucesso={bool(ok)} erros={err[:2]}")
            if ok:
                break
        print("   URL final:", pg.url)
        print("\n   --- rede POST/PUT ---")
        for t in rede:
            if not any(x in t[2] for x in ("google", "facebook", "sentry", "hotjar", "clarity")):
                print("   ", t)
        pg.screenshot(path=os.path.join(BASE, "_tmp", "talenthq-enviado.png"), full_page=True)
    else:
        print("\n[8] DRY-RUN: nada enviado.")
        pg.screenshot(path=os.path.join(BASE, "_tmp", "talenthq-dry.png"), full_page=True)

    ctx.close()
    b.close()
