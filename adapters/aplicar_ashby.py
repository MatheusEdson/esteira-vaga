"""Adaptador Ashby (jobs.ashbyhq.com). Casa as perguntas pelo TEXTO do label.

  python aplicar_ashby.py <url> --respostas respostas-elevenlabs.md [--submit]

Aborta sem enviar se achar pergunta obrigatoria sem resposta preparada.
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

if len(sys.argv) < 2:
    raise SystemExit(__doc__)
URL = sys.argv[1]
DO_SUBMIT = "--submit" in sys.argv
MD = sys.argv[sys.argv.index("--respostas") + 1] if "--respostas" in sys.argv else None
trilha = sys.argv[sys.argv.index("--cv") + 1] if "--cv" in sys.argv else "web_seo"
CV = os.path.join(BASE, PERFIL["curriculos"][trilha])
print(f"[0] CV: {os.path.basename(CV)}")


def secoes(md):
    """Le o .md e devolve {trecho_da_pergunta: resposta}."""
    txt = open(os.path.join(BASE, md), encoding="utf-8").read()
    out = {}
    for bloco in re.split(r"\n## ", txt)[1:]:
        cab, _, corpo = bloco.partition("\n")
        corpo = corpo.split("\n---")[0].strip()
        # o cabecalho traz a pergunta depois do ultimo ' · '
        pergunta = cab.split("·")[-1].strip().rstrip("?").lower()
        if corpo and not cab.lower().startswith("campos"):
            out[pergunta] = corpo
    return out


RESP = secoes(MD) if MD else {}
print(f"[0] {len(RESP)} respostas carregadas de {MD}")


def casar(label):
    """Acha a resposta cujo texto de pergunta melhor bate com o label do form."""
    lab = re.sub(r"[^a-z0-9 ]", " ", label.lower())
    melhor, score_max = None, 0
    for pergunta, resposta in RESP.items():
        p = re.sub(r"[^a-z0-9 ]", " ", pergunta)
        palavras = [w for w in p.split() if len(w) > 3]
        if not palavras:
            continue
        score = sum(1 for w in palavras if w in lab) / len(palavras)
        if score > score_max:
            melhor, score_max = resposta, score
    return (melhor, score_max) if score_max >= 0.5 else (None, score_max)


with sync_playwright() as p:
    b = p.chromium.launch(headless=True, channel="msedge")
    ctx = b.new_context(viewport={"width": 1400, "height": 1100}, locale="en-US")
    pg = ctx.new_page()
    print("[1]", URL)
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(4000)
    if "/application" not in pg.url:
        try:
            pg.locator("a:has-text('Apply'), button:has-text('Apply')").first.click(timeout=10000)
            pg.wait_for_timeout(3000)
        except Exception:
            pass

    print("[2] campos basicos")
    pg.fill("input[name='_systemfield_name']", ID["nome_completo"])
    pg.fill("input[name='_systemfield_email']", ID["email"])
    # Location e' autocomplete: digitar e escolher a primeira sugestao
    try:
        loc = pg.get_by_placeholder("Start typing...").first
        loc.fill("Brazil")
        pg.wait_for_timeout(2500)
        pg.keyboard.press("ArrowDown")
        pg.keyboard.press("Enter")
        print("   location: Brazil")
    except Exception as e:
        print("   location falhou:", repr(e)[:60])

    print("[3] curriculo")
    inputs = pg.evaluate("""() => [...document.querySelectorAll('input[type=file]')]
        .map((e, i) => ({i, name: e.name || '', id: e.id || '',
                         aria: e.getAttribute('aria-label') || ''}))""")
    print("   file inputs:", inputs)
    # o de curriculo e' o que tem _systemfield_resume; senao, o ultimo
    alvo = next((f["i"] for f in inputs if "resume" in (f["name"] + f["id"] + f["aria"]).lower()),
                len(inputs) - 1)
    pg.locator("input[type=file]").nth(alvo).set_input_files(CV)
    pg.wait_for_timeout(7000)
    anexado = pg.evaluate("""() => /\\.pdf/i.test(document.body.innerText)""")
    print(f"   slot {alvo} <- {os.path.basename(CV)} | pdf visivel na pagina: {anexado}")

    print("[4] 'How did you hear' -> Job board")
    try:
        pg.get_by_text("Job board", exact=True).first.click(timeout=8000)
    except Exception as e:
        print("   falhou:", repr(e)[:60])

    print("[5] perguntas")
    campos = pg.evaluate("""() => [...document.querySelectorAll('input[type=text], textarea')]
      .filter(e => e.offsetParent !== null && !/_systemfield/.test(e.name || ''))
      .map(e => {
        let lab = '', p = e.closest('div');
        for (let i = 0; i < 6 && p; i++) {
          const l = p.querySelector('label');
          if (l && l.innerText.trim().length > 5) { lab = l.innerText.trim(); break; }
          p = p.parentElement;
        }
        return {name: e.name || '', tag: e.tagName.toLowerCase(),
                label: lab.replace(/\\s+/g, ' ').slice(0, 150),
                req: /\\*|required/i.test(lab)};
      })""")

    bloqueios = []
    for c in campos:
        if not c["label"]:
            continue
        if re.search(r"linkedin", c["label"], re.I):
            pg.fill(f"[name='{c['name']}']", ID["linkedin_url"])
            print(f"   [linkedin] {c['label'][:60]}")
            continue
        if re.search(r"if other, please specify", c["label"], re.I):
            continue
        resposta, score = casar(c["label"])
        if resposta:
            pg.fill(f"[name='{c['name']}']", resposta)
            print(f"   [ok {score:.2f}] {c['label'][:64]} ({len(resposta)} chars)")
        else:
            marca = "REQ" if c["req"] else "opc"
            print(f"   [{marca} SEM RESPOSTA {score:.2f}] {c['label'][:64]}")
            if c["req"]:
                bloqueios.append(c["label"])

    if bloqueios:
        print("\n" + "=" * 76)
        print("ABORTADO. Pergunta obrigatoria sem resposta preparada:")
        for x in bloqueios:
            print("  *", x)
        print("=" * 76)
        ctx.close(); b.close(); raise SystemExit(2)

    pg.screenshot(path=os.path.join(BASE, "_tmp", "ashby-preenchido.png"), full_page=True)

    if DO_SUBMIT:
        print("\n[6] ENVIANDO")
        bt = pg.locator("button:has-text('Submit Application')").first
        bt.scroll_into_view_if_needed()
        pg.wait_for_timeout(1200)
        print("   botao visivel:", bt.is_visible(), "| desabilitado:", bt.is_disabled())
        bt.click()
        slug = re.sub(r"[^a-z0-9]+", "-", URL.split("ashbyhq.com/")[-1].lower())[:40]
        for i in range(12):
            pg.wait_for_timeout(3000)
            corpo = pg.inner_text("body")
            # ATENCAO: "botao sumiu" NAO e' sucesso. Quando o Ashby marca a submissao
            # como spam ele TAMBEM troca o form pela mensagem de erro, e o botao some.
            spam = re.search(r"flagged as possible spam|couldn.t submit your application", corpo, re.I)
            ok = re.search(r"thank you for applying|application (was )?(submitted|received)|"
                           r"we.ve received your application", corpo, re.I)
            erro = [l.strip() for l in corpo.split("\n")
                    if re.search(r"is required|please (fill|complete|enter)|invalid|captcha", l, re.I)]
            print(f"   t={3*(i+1):>2}s sucesso={bool(ok)} SPAM={bool(spam)} erros={erro[:2]}")
            if ok or spam:
                break
        print("   URL final:", pg.url)
        pg.screenshot(path=os.path.join(BASE, "_tmp", f"ashby-{slug}.png"), full_page=True)
        print("   screenshot:", f"ashby-{slug}.png")
    else:
        print("\n[6] DRY-RUN: nada enviado.")

    ctx.close()
    b.close()
