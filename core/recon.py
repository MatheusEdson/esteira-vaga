"""Mapeia um formulario de candidatura desconhecido.

  python recon.py <url> [<url> ...]

Imprime todo campo com label, obrigatoriedade e opcoes, mais o texto visivel do
form, e salva screenshot em _tmp/recon-<n>.png.
"""
import sys, os
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py

BASE = os.path.dirname(os.path.abspath(__file__))
URLS = sys.argv[1:]
if not URLS:
    raise SystemExit(__doc__)

CAMPOS = r"""() => {
  const rotulo = (el) => {
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                 if (l && l.innerText.trim()) return l.innerText.trim(); }
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
    let p = el.closest('div, fieldset, li, section');
    for (let i = 0; i < 6 && p; i++) {
      const l = p.querySelector('label, legend');
      if (l && l.innerText.trim().length > 2) return l.innerText.trim();
      p = p.parentElement;
    }
    return '';
  };
  return [...document.querySelectorAll('input, textarea, select')]
    .filter(e => !['hidden','submit','button'].includes(e.type))
    .map(e => ({
      tag: e.tagName.toLowerCase(), type: e.type,
      name: e.name || '', id: e.id || '',
      required: e.required || e.getAttribute('aria-required') === 'true',
      placeholder: e.placeholder || '',
      value: (e.type === 'radio' || e.type === 'checkbox') ? e.value : '',
      label: rotulo(e).replace(/\s+/g, ' ').slice(0, 160),
      options: e.tagName === 'SELECT' ? [...e.options].map(o => o.text).slice(0, 15) : [],
      visivel: e.offsetParent !== null,
    }));
}"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, channel="msedge")
    ctx = b.new_context(viewport={"width": 1440, "height": 1200}, locale="en-US")
    for n, url in enumerate(URLS, 1):
        pg = ctx.new_page()
        print("\n" + "#" * 92)
        print(f"### {url}")
        print("#" * 92)
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=90000)
            pg.wait_for_timeout(4000)
            for sel in ["button:has-text('Accept')", "button:has-text('Aceitar')",
                        "button:has-text('Got it')", "button:has-text('OK')"]:
                try:
                    bt = pg.locator(sel).first
                    if bt.is_visible(timeout=1200):
                        bt.click(); pg.wait_for_timeout(800); break
                except Exception:
                    pass
            # tenta revelar o form
            for sel in ["a:has-text('Apply')", "button:has-text('Apply')",
                        "button:has-text('Candidatar')", "a:has-text('Candidatar')"]:
                try:
                    bt = pg.locator(sel).first
                    if bt.is_visible(timeout=1200):
                        bt.click(); pg.wait_for_timeout(3000); break
                except Exception:
                    pass

            print("URL final:", pg.url)
            print("titulo   :", pg.title()[:110])
            campos = pg.evaluate(CAMPOS)
            print(f"\n--- {len(campos)} campos ---")
            for c in campos:
                req = "REQ" if c["required"] else "   "
                vis = "" if c["visivel"] else " [oculto]"
                extra = f' = "{c["value"]}"' if c["value"] else ""
                print(f'[{req}] {c["tag"]}/{c["type"]:<9} {c["name"] or c["id"]}{extra}{vis}')
                if c["label"]:
                    print(f'        LABEL: {c["label"]}')
                if c["placeholder"]:
                    print(f'        PLACE: {c["placeholder"]}')
                if c["options"]:
                    print(f'        OPTS : {c["options"]}')

            print("\n--- texto do form ---")
            txt = pg.evaluate("""() => { const f = document.querySelector('form');
                                 return (f || document.body).innerText; }""")
            visto = set()
            for l in [x.strip() for x in txt.split("\n")]:
                if l and l not in visto:
                    visto.add(l)
                    print("  ", l[:120])

            print("\n--- botoes ---")
            for x in pg.evaluate("""() => [...document.querySelectorAll('button, input[type=submit]')]
                    .map(e => ((e.innerText || e.value || '').trim().slice(0,60)))
                    .filter(t => t)"""):
                print("  ", x)

            pg.screenshot(path=os.path.join(BASE, "_tmp", f"recon-{n}.png"), full_page=True)
        except Exception as e:
            print("ERRO:", repr(e)[:200])
        pg.close()
    ctx.close()
    b.close()
