"""Resolve o link REAL de candidatura a partir da URL publica da vaga no LinkedIn,
sem login. Se der certo, as vagas EXTERNAL podem ser aplicadas sem sessao.

  python resolver_apply.py <url> [<url> ...]
"""
import sys, os, json
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py

BASE = os.path.dirname(os.path.abspath(__file__))
URLS = sys.argv[1:]
if not URLS:
    raise SystemExit(__doc__)

resultados = []

with sync_playwright() as p:
    # usa a sessao logada do LinkedIn: sem ela o botao de apply cai em signup/cold-join
    ctx = p.chromium.launch_persistent_context(
        os.path.join(BASE, "_tmp", "edge-profile-linkedin"), channel="msedge", headless=True,
        viewport={"width": 1400, "height": 1000}, locale="en-US",
        )

    for url in URLS:
        pg = ctx.new_page()
        alvo, via = "", ""
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(3500)
            try:
                pg.locator("button:has-text('Dismiss'), button[aria-label*='Dismiss']").first.click(timeout=2500)
                pg.wait_for_timeout(800)
            except Exception:
                pass

            # 1) link de apply externo exposto no HTML
            achado = pg.evaluate("""() => {
              const out = [];
              document.querySelectorAll('a, button').forEach(e => {
                const h = e.getAttribute('href') || '';
                const t = (e.innerText || '').trim();
                if (/externalApply|applyUrl|offsite/i.test(h) || /apply/i.test(t))
                  out.push({t: t.slice(0, 40), h: h.slice(0, 300)});
              });
              return out;
            }""")
            ext = [a for a in achado if "externalApply" in a["h"] or "offsite" in a["h"]]
            if ext:
                alvo, via = ext[0]["h"], "href externalApply"

            # 2) no JSON embutido da pagina
            if not alvo:
                m = pg.evaluate("""() => {
                  const s = document.documentElement.innerHTML;
                  const m = s.match(/"companyApplyUrl"\\s*:\\s*"([^"]+)"/) ||
                            s.match(/"applyUrl"\\s*:\\s*"([^"]+)"/) ||
                            s.match(/externalApply[^"']*/);
                  return m ? m[1] || m[0] : '';
                }""")
                if m:
                    alvo, via = m.replace("\\u0026", "&"), "json embutido"

            # 2.5) logado, o botao abre ABA NOVA por JS: clicar e capturar o popup
            if not alvo:
                try:
                    # a conta dele esta em pt-BR: o botao e' "Candidatar-se"
                    bt = pg.locator(
                        "button:has-text('Candidatar'), a:has-text('Candidatar'), "
                        "button:has-text('Apply'), a:has-text('Apply')").first
                    bt.wait_for(state="visible", timeout=12000)
                    with ctx.expect_page(timeout=20000) as nova:
                        bt.click()
                    pop = nova.value
                    pop.wait_for_load_state("domcontentloaded", timeout=25000)
                    pop.wait_for_timeout(3000)
                    alvo, via = pop.url, "popup do botao Apply"
                    pop.close()
                except Exception as e:
                    via = f"popup falhou: {repr(e)[:50]}"

            # 3) seguir o redirect do externalApply
            if alvo and "externalApply" in alvo:
                full = alvo if alvo.startswith("http") else "https://www.linkedin.com" + alvo
                pg2 = ctx.new_page()
                try:
                    pg2.goto(full, wait_until="domcontentloaded", timeout=45000)
                    pg2.wait_for_timeout(4000)
                    alvo, via = pg2.url, via + " -> redirect"
                except Exception as e:
                    via += f" (redirect falhou: {repr(e)[:40]})"
                pg2.close()

            titulo = pg.title()[:70]
            login_wall = "sign in" in pg.inner_text("body").lower()[:1500]
        except Exception as e:
            titulo, login_wall = f"ERRO {repr(e)[:60]}", None

        print(f"\n{url}")
        print(f"  titulo    : {titulo}")
        print(f"  login wall: {login_wall}")
        print(f"  via       : {via or '(nao resolveu)'}")
        print(f"  DESTINO   : {alvo or '(vazio)'}")
        resultados.append({"vaga": url, "destino": alvo, "via": via})
        pg.close()

    ctx.close()

with open(os.path.join(BASE, "_tmp", "apply-urls.json"), "w", encoding="utf-8") as f:
    json.dump(resultados, f, ensure_ascii=False, indent=2)
print("\nsalvo em _tmp/apply-urls.json")
