"""Abre as vagas da Remote Talent LATAM numa janela VISIVEL, ja' preenchidas.

Deixa em branco so' o campo do Vocaroo. Voce cola o link e clica em Submit.
A janela fica aberta ate' voce fechar.

  python preencher_workable.py
"""
import os, sys, re, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.bootstrap import PERFIL, ID, cv, bloco, tmp, sync_playwright

ENVIAR = "--enviar" in sys.argv

CV = cv("web_seo")
SALARIO = str(PERFIL["respostas_padrao"].get("expected_salary_usd_month") or "")

MULTI_LOCAL = bloco("MULTI_LOCAL")
MAIOR_MULTI = (
    "Most of my portfolio is single-location, so I want to be straight about this: I have not run a single "
    "account with dozens of branches. The largest multi-site account I managed was an industrial group with "
    "three sub-brands and two physical locations."
)
QTD_SEO = (
    "Around fifteen at the same time, as Head of Paid Media and SEO at the agency, across both SEO and paid "
    "media for the same accounts."
)
INDUSTRIAS = bloco("INDUSTRIAS")

# pergunta (regex no label) -> resposta. Booleanos usam True/False.
VOCAROO = PERFIL["anexos"]["vocaroo_30s"]

REGRAS = [
    # 14/08: o Matheus afirmou ter os 5 anos e pediu YES. Registrado que a decisao
    # e' dele; a timeline do CV anexado mostra menos que isso.
    (r"at least 5 years of hands-on google ads",              True),
    (r"vocaroo",                                              VOCAROO),
    (r"directly managing and optimizing google ads",          True),
    (r"microsoft excel",                                      True),
    (r"managed google ads campaigns for local service",       MULTI_LOCAL),
    (r"largest multi-location account",                       MAIOR_MULTI),
    (r"managing seo clients directly",                        True),
    (r"how many seo client accounts",                         QTD_SEO),
    (r"what industries have you managed seo",                 INDUSTRIAS),
    (r"linkedin",                                             ID["linkedin_url"]),
    (r"salary expectation|salary expectations",               SALARIO),
]

VAGAS = [
    ("Senior PPC Account Manager", "https://apply.workable.com/remote-talent-latam/j/DE3B3BF5FB/apply/"),
    ("SEO Account Manager",        "https://apply.workable.com/remote-talent-latam/j/F2DDBE1FA5/apply/"),
]

MAPEAR = r"""() => [...document.querySelectorAll('input, textarea')]
  .filter(e => !['hidden','submit','button','file'].includes(e.type))
  .map(e => {
    let lab = '', p = e.closest('div, li, fieldset');
    for (let i = 0; i < 6 && p; i++) {
      const l = p.querySelector('label, legend');
      if (l && l.innerText.trim().length > 4) { lab = l.innerText.trim(); break; }
      p = p.parentElement;
    }
    return {name: e.name || '', type: e.type, val: e.value || '',
            label: lab.replace(/\s+/g, ' ').slice(0, 160)};
  })"""

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        tmp("edge-profile-workable"), channel="msedge", headless=ENVIAR,
        viewport={"width": 1500, "height": 1000}, locale="en-US",
        )

    for nome, url in VAGAS:
        pg = ctx.new_page()
        print(f"\n=== {nome} ===")
        pg.goto(url, wait_until="domcontentloaded", timeout=90000)
        pg.wait_for_timeout(5000)
        for sel in ["button:has-text('Accept')", "button:has-text('Got it')"]:
            try:
                bt = pg.locator(sel).first
                if bt.is_visible(timeout=1500):
                    bt.click(); pg.wait_for_timeout(600); break
            except Exception:
                pass

        for campo, valor in (("firstname", ID["first_name"]), ("lastname", ID["last_name"]),
                             ("email", ID["email"]), ("phone", ID["telefone_e164"]),
                             ("address", "%s, %s, %s" % (ID["cidade"], ID["estado"], ID["pais"]))):
            try:
                pg.fill(f"input[name='{campo}']", valor)
            except Exception as e:
                print(f"  {campo}: {repr(e)[:45]}")
        print("  dados pessoais ok")

        try:
            pg.locator("input[type=file]").first.set_input_files(CV)
            pg.wait_for_timeout(5000)
            print("  curriculo:", os.path.basename(CV))
        except Exception as e:
            print("  curriculo falhou:", repr(e)[:60])

        # radios primeiro: o label deles e' so' "YES"/"NO", entao a pergunta precisa
        # ser buscada subindo o DOM ate' achar texto de verdade
        grupos = pg.evaluate("""() => {
            const out = {};
            document.querySelectorAll('input[type=radio]').forEach(e => {
              if (!e.name || out[e.name]) return;
              let p = e, q = '';
              for (let i = 0; i < 8 && p; i++) {
                // a primeira linha costuma ser so' o "*" de obrigatorio e as ultimas
                // sao "YES"/"NO": pegar a linha mais LONGA que sobra
                const linhas = (p.innerText || '').split('\\n')
                  .map(s => s.trim())
                  .filter(s => s.length > 12 && !/^(yes|no|\\*)$/i.test(s));
                if (linhas.length) {
                  q = linhas.sort((a, b) => b.length - a.length)[0];
                  break;
                }
                p = p.parentElement;
              }
              out[e.name] = q;
            });
            return out;
          }""")
        for nome_g, pergunta in grupos.items():
            resp = next((v for k, v in REGRAS if re.search(k, pergunta.lower())), None)
            if isinstance(resp, bool):
                pg.evaluate("""([n, v]) => { const el = document.querySelector(
                      `input[name="${n}"][value="${v}"]`); if (el) el.click(); }""",
                    [nome_g, "true" if resp else "false"])
                print(f"  [sim/nao] {pergunta[:62]} -> {'YES' if resp else 'NO'}")
            else:
                print(f"  [!! SEM RESPOSTA] {pergunta[:70]}")

        campos = pg.evaluate(MAPEAR)
        pendentes = []
        for c in campos:
            lab = c["label"].lower()
            if c["type"] == "radio":
                continue
            if not lab or not c["name"] or c["name"] in ("firstname", "lastname", "email",
                                                         "phone", "address", "city", "postcode", "country"):
                continue
            resp = next((v for k, v in REGRAS if re.search(k, lab)), None)
            if resp is None:
                pendentes.append(c["label"][:70])
                continue
            if isinstance(resp, bool):
                pg.evaluate("""([n, v]) => { const el = document.querySelector(
                      `input[name="${n}"][value="${v}"]`); if (el) el.click(); }""",
                    [c["name"], "true" if resp else "false"])
                print(f"  [sim/nao] {c['label'][:58]} -> {'YES' if resp else 'NO'}")
            else:
                try:
                    pg.fill(f"[name='{c['name']}']", str(resp))
                    print(f"  [texto]   {c['label'][:58]} -> {str(resp)[:40]}...")
                except Exception as e:
                    print(f"  [FALHOU]  {c['label'][:58]} {repr(e)[:40]}")

        if pendentes:
            print("  FALTA VOCE:", " | ".join(sorted(set(pendentes))))

        # CAUSA RAIZ do "submitting" eterno: um <div data-ui="backdrop"> cobre a pagina
        # e intercepta o ponteiro. fill() nao precisa de ponteiro, entao os campos
        # preenchiam e SO' o clique no botao era engolido, sem erro nenhum na tela.
        # Limpar SEMPRE, inclusive quando quem clica e' o Matheus.
        for sel in ["button:has-text('Accept all')", "button:has-text('Accept')"]:
            try:
                bc = pg.locator(sel).first
                if bc.is_visible(timeout=3000):
                    bc.click()
                    print(f"  cookies aceitos ({sel})")
                    pg.wait_for_timeout(1200)
                    break
            except Exception:
                pass
        sobrou = pg.evaluate("""() => {
            const bs = [...document.querySelectorAll('[data-ui="backdrop"]')];
            bs.forEach(b => b.remove());
            return bs.length;
          }""")
        print(f"  backdrops removidos: {sobrou}")

        ja_aplicou = pg.evaluate("""() => /already applied|you have applied/i
            .test(document.body.innerText)""")
        if ja_aplicou:
            print("  >>> A PAGINA DIZ QUE VOCE JA APLICOU NESSA VAGA")

        if ENVIAR:
            bt = pg.locator("button:has-text('Submit application')").first
            bt.scroll_into_view_if_needed()
            pg.wait_for_timeout(1500)
            print(f"  botao desabilitado: {bt.is_disabled()}")
            bt.click()
            for i in range(14):
                pg.wait_for_timeout(3000)
                corpo = pg.inner_text("body")
                ok = re.search(r"thank you|application (was )?(submitted|received)|"
                               r"we.ve received|successfully", corpo, re.I)
                erro = [l.strip() for l in corpo.split("\n")
                        if re.search(r"is required|please (fill|enter|select|complete)|invalid", l, re.I)]
                print(f"    t={3*(i+1):>2}s sucesso={bool(ok)} erros={erro[:3]}")
                if ok:
                    break
            print("    URL:", pg.url)
            slug = re.sub(r"[^a-z0-9]+", "-", nome.lower())
            pg.screenshot(path=tmp(f"wk-{slug}.png"), full_page=True)

    print("\n" + "=" * 76)
    if ENVIAR:
        print("Rodada de envio concluida. Confira os screenshots em _tmp/wk-*.png")
    else:
        print("As duas abas estao abertas e preenchidas. Clique em Submit application.")
        print("A janela fica aberta. Feche o browser quando terminar.")
    print("=" * 76)
    if not ENVIAR:
        try:
            while len(ctx.pages) > 0:
                time.sleep(5)
        except Exception:
            pass
    ctx.close()
