"""Adaptador Teamtailor: preenche e envia candidatura em QUALQUER careers site Teamtailor.

Casa as perguntas pelo TEXTO do label, nao por indice, para funcionar em sites diferentes.
Se encontrar pergunta obrigatoria sem resposta verdadeira no perfil.json, ABORTA sem enviar
e imprime a pergunta literal. Isso e' proposital: e' o guardrail de integridade.

Uso:
  python aplicar_teamtailor.py <url-da-vaga> --cv web_seo
  python aplicar_teamtailor.py <url-da-vaga> --cv paid_seo --submit
"""
import sys, os, re
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py

BASE = os.path.dirname(os.path.abspath(__file__))
from core.perfil import perfil as _carregar_perfil   # le data/perfil.json
PERFIL = _carregar_perfil()
from core.perfil import curriculo as _cv, anexo as _anexo
ID, RESP, DELIC = PERFIL["identidade"], PERFIL["respostas_padrao"], PERFIL["respostas_delicadas"]

# ------------------------------------------------------------------ argumentos
if len(sys.argv) < 2:
    raise SystemExit(__doc__)
URL = sys.argv[1]
DO_SUBMIT = "--submit" in sys.argv
trilha = "web_seo"
if "--cv" in sys.argv:
    trilha = sys.argv[sys.argv.index("--cv") + 1]
# Cada vaga publica uma faixa propria. Pedir o valor global do perfil subprecifica numa vaga
# de dev e elimina numa vaga de especialista. --salario forca o topo da faixa DAQUELA vaga.
if "--salario" in sys.argv:
    PERFIL["respostas_padrao"]["expected_salary_usd_month"] = \
        sys.argv[sys.argv.index("--salario") + 1]
CV = _cv(trilha)
SPEED = _anexo("speedtest")
for f in (CV, SPEED):
    if not os.path.exists(f):
        raise SystemExit(f"ERRO: nao achei {f}")

# ------------------------------------- de pergunta para resposta (ordem importa)
REGRAS = [
    (r"how did you hear",                        ("choice",  RESP["how_did_you_hear"])),
    (r"internet speed|speed ?test",              ("upload",  SPEED)),
    (r"expected.*salary|salary expectation|desired (monthly )?(salary|compensation)",
                                                 ("valor",   RESP["expected_salary_usd_month"])),
    (r"how soon|when can you (start|join)|availability|notice period|start date",
                                                 ("valor",   RESP["availability_start"])),
    (r"emergency contact",                       ("valor",   ID["contato_emergencia"])),
    # perguntas que expoem gap: resposta honesta pre-escrita
    (r"experience working with a us law firm|worked with a us law firm",
                                                 ("bool",    False)),
    (r"links? to the us law firms?|us law firms you.*worked",
                                                 ("valor",   DELIC["us_law_firm_links"])),
    (r"experience (working )?in digital marketing agenc|worked (in|for) .*agenc",
                                                 ("bool",    RESP["experiencia_agencia_marketing"])),
    (r"link of the digital marketing agency|agency you have worked",
                                                 ("valor",   RESP["experiencia_agencia_texto"])),
    (r"us-based clients|clients or organizations|worked with (us|american) (clients|companies)",
                                                 ("bool",    RESP["experiencia_clientes_eua"])),
    (r"years? of experience.*(seo|search)",      ("valor",   RESP["anos_experiencia_seo"])),
    (r"years? of experience.*(paid|ads|ppc|media)", ("valor", RESP["anos_experiencia_paid_media"])),
    (r"years? of experience.*wordpress",         ("valor",   RESP["anos_experiencia_wordpress"])),
    # dissertativa de WordPress: vem ANTES da regra generica de "years of experience"
    (r"experience in wordpress|experience with wordpress",
                                                 ("valor",   RESP["wordpress_experiencia"])),
    (r"figma",                                   ("valor",   RESP["figma_experiencia"])),
    (r"healthcare|dental|dentist",               ("valor",   RESP["healthcare_dental_clientes"])),
    (r"years? of experience",                    ("valor",   RESP["anos_experiencia_seo"])),
    (r"english|proficiency in english",          ("valor",   RESP["ingles_nivel"])),
    (r"work (remotely|from home)|comfortable working remote", ("bool", RESP["remoto_ok"])),
    (r"us (hours|time ?zone)|work.*(mountain|central|pacific|eastern) time",
                                                 ("bool",    RESP["willing_to_work_us_hours"])),
    (r"linkedin (profile|url)",                  ("valor",   ID["linkedin_url"])),
    (r"portfolio|personal (web)?site|your website", ("valor", ID["portfolio"][0])),
    (r"upload cv|resume|curriculum",             ("upload",  CV)),
    (r"additional files|cover letter",           ("skip",    None)),
]


def resolver(label):
    lab = label.lower()
    for padrao, (tipo, valor) in REGRAS:
        if re.search(padrao, lab):
            if valor == "PENDENTE_CONFIRMAR":
                return None, None  # nao inventar
            return tipo, valor
    return None, None


# ------------------------------------------------------- leitura das perguntas
MAPEAR = r"""() => {
  // o label da PERGUNTA no Teamtailor tem class font-medium; os labels de OPCAO
  // usam choice-input-wrapper__label. Preferir o primeiro, senao pega opcao por engano.
  const rotulo = (el) => {
    let p = el.closest('div, fieldset, li');
    for (let i = 0; i < 8 && p; i++) {
      const q = p.querySelector('label[class*="font-medium"], legend');
      if (q && q.innerText.trim().length > 3) return q.innerText.trim();
      p = p.parentElement;
    }
    p = el.closest('div, fieldset, li');
    for (let i = 0; i < 6 && p; i++) {
      const l = p.querySelector('label:not([class*="choice-input"]), legend');
      if (l && l.innerText.trim().length > 3) return l.innerText.trim();
      p = p.parentElement;
    }
    return '';
  };
  const qs = {};
  // inclui hidden: e' assim que a pergunta de UPLOAD se revela (upload_attributes)
  document.querySelectorAll('input, textarea, select').forEach(el => {
    if (['submit','button'].includes(el.type)) return;
    // normaliza colchetes para underscore: candidate[answers_attributes][5][boolean]
    // e candidate_answers_attributes_0_choice_5 viram a mesma forma
    const norm = ((el.name || '') + ' ' + (el.id || '')).replace(/[\[\]]+/g, '_');
    const m = norm.match(/answers_attributes_+(\d+)_+([a-zA-Z]+)/);
    if (!m) return;
    const [, idx, kind] = m;
    const label = rotulo(el);
    qs[idx] = qs[idx] || {idx, kinds: {}, label: '', required: false};
    if (el.type !== 'hidden' && el.name) qs[idx].kinds[kind] = el.name;
    if (/upload/i.test(kind)) qs[idx].kinds['upload'] = true;
    if (label.length > qs[idx].label.length) qs[idx].label = label;
    if (/\*|Required/i.test(label)) qs[idx].required = true;
  });
  return Object.values(qs).map(q => ({...q,
    label: q.label.replace(/\s*\*?\s*Required\s*$/i, '').replace(/\s+/g, ' ').trim()}));
}"""

# de qual pergunta cada input[type=file] pertence, via o hidden *_remote_url vizinho
DONO_DOS_UPLOADS = r"""() => {
  return [...document.querySelectorAll('input[type=file]')].map((e, i) => {
    let p = e, dono = '';
    for (let k = 0; k < 8 && p; k++) {
      const h = p.querySelector('input[id*="remote_url"]');
      if (h) { dono = h.id; break; }
      p = p.parentElement;
    }
    return {i, dono};
  });
}"""


def espera_upload(pg, hidden_regex, rotulo):
    for i in range(15):
        pg.wait_for_timeout(2000)
        ok = pg.evaluate("""(rx) => [...document.querySelectorAll('input')]
              .some(e => new RegExp(rx).test(e.name || '') && e.value)""", hidden_regex)
        if ok:
            print(f"      upload {rotulo}: OK em {2*(i+1)}s")
            return True
    print(f"      upload {rotulo}: NAO CONFIRMADO")
    return False


with sync_playwright() as p:
    b = p.chromium.launch(headless=True, channel="msedge")
    ctx = b.new_context(viewport={"width": 1440, "height": 1100}, locale="en-US")
    pg = ctx.new_page()

    print(f"[1] {URL}")
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(2500)
    for sel in ["button:has-text('Accept all')", "button:has-text('Accept')"]:
        try:
            bt = pg.locator(sel).first
            if bt.is_visible(timeout=1500):
                bt.click(); pg.wait_for_timeout(600); break
        except Exception:
            pass

    print("[2] abrindo formulario")
    try:
        pg.locator("button:has-text('APPLY')").first.click(timeout=20000)
    except Exception:
        pass
    pg.wait_for_selector("input[name='candidate[first_name]']", timeout=60000)
    pg.wait_for_timeout(1500)

    print("[3] perguntas encontradas:")
    perguntas = pg.evaluate(MAPEAR)
    bloqueios = []
    for q in perguntas:
        tipo, valor = resolver(q["label"])
        marca = {"choice": "escolha", "bool": "sim/nao", "valor": "texto",
                 "upload": "arquivo", "skip": "ignorar", None: "SEM RESPOSTA"}[tipo]
        print(f"   [{q['idx']}] {marca:>12} | {q['label'][:78]}")
        if tipo is None and q["required"]:
            bloqueios.append(q["label"])

    # o upload de arquivo nem sempre aparece como answers_attributes: tratar por posicao
    finputs = pg.locator("input[type=file]")
    n_files = finputs.count()

    if bloqueios:
        print("\n" + "=" * 78)
        print("ABORTADO SEM ENVIAR. Pergunta obrigatoria sem resposta verdadeira no perfil.json:")
        for x in bloqueios:
            print("  *", x)
        print("Adicione a resposta em perfil.json (ou responda na mao) e rode de novo.")
        print("=" * 78)
        ctx.close(); b.close()
        raise SystemExit(2)

    print("\n[4] preenchendo")
    for q in perguntas:
        tipo, valor = resolver(q["label"])
        if tipo in (None, "skip", "upload"):
            continue
        k = q["kinds"]
        if tipo == "choice" and "choice" in k:
            try:
                pg.locator("button:has-text('Select an option')").first.click(timeout=6000)
                pg.wait_for_timeout(600)
                pg.get_by_role("button", name=str(valor), exact=True).first.click(timeout=6000)
            except Exception:
                pg.evaluate("""([n, t]) => { const o = [...document.querySelectorAll(`input[name="${n}"]`)];
                    const el = o.find(e => { const l = document.querySelector(`label[for="${e.id}"]`);
                      return l && l.innerText.trim().toLowerCase() === t.toLowerCase(); }) || o[0];
                    el.checked = true; el.dispatchEvent(new Event('change', {bubbles:true})); }""",
                    [k["choice"], str(valor)])
            print(f"   [{q['idx']}] escolha = {valor}")
        elif tipo == "bool" and "boolean" in k:
            pg.evaluate("""([n, v]) => { const el = document.querySelector(`input[name="${n}"][value="${v}"]`);
                  if (el) { el.click(); } }""", [k["boolean"], "true" if valor else "false"])
            print(f"   [{q['idx']}] sim/nao = {valor}")
        elif tipo == "valor":
            campo = k.get("text") or k.get("number")
            if campo:
                pg.fill(f"[name='{campo}']", str(valor))
                print(f"   [{q['idx']}] texto = {str(valor)[:60]}")

    print("[5] uploads")
    donos = pg.evaluate(DONO_DOS_UPLOADS)
    # indice da pergunta que pede o speedtest, se existir
    idx_speed = next((q["idx"] for q in perguntas
                      if re.search(r"internet speed|speed ?test", q["label"], re.I)), None)
    for d in donos:
        dono = d["dono"]
        if dono == "candidate_resume_remote_url":
            finputs.nth(d["i"]).set_input_files(CV)
            print(f"   slot {d['i']} = CV ({os.path.basename(CV)})")
            espera_upload(pg, r"resume_remote_url", "cv")
        elif idx_speed is not None and f"answers_attributes_{idx_speed}_" in dono:
            finputs.nth(d["i"]).set_input_files(SPEED)
            print(f"   slot {d['i']} = speedtest")
            espera_upload(pg, rf"answers_attributes\]\[{idx_speed}\].*file_remote_url", "speedtest")
        else:
            print(f"   slot {d['i']} = ignorado ({dono or 'sem dono'})")

    print("[6] dados pessoais")
    for campo, val in (("first_name", ID["first_name"]), ("last_name", ID["last_name"]),
                       ("email", ID["email"]), ("phone", ID["telefone_e164"])):
        try:
            pg.fill(f"input[name='candidate[{campo}]']", val)
        except Exception as e:
            print(f"   {campo}: falhou {repr(e)[:50]}")

    print("[7] consentimento (property set: clicar no label cai no link da Privacy Policy)")
    for cid in ("candidate_consent_given", "candidate_consent_given_future_jobs"):
        st = pg.evaluate("""(i) => { const el = document.getElementById(i);
              if (!el) return 'ausente'; el.checked = true;
              el.dispatchEvent(new Event('input', {bubbles:true}));
              el.dispatchEvent(new Event('change', {bubbles:true})); return el.checked; }""", cid)
        print(f"   {cid}: {st}")

    slug = re.sub(r"[^a-z0-9]+", "-", URL.split("/jobs/")[-1].lower())[:50]
    pg.locator("section.overlay").first.screenshot(
        path=os.path.join(BASE, "_tmp", f"form-{slug}.png"))

    if DO_SUBMIT:
        print("\n[8] ENVIANDO")
        sb = pg.locator("input[type=submit][value*='Submit'], button[type=submit]").first
        sb.scroll_into_view_if_needed()
        sb.click()
        pg.wait_for_timeout(9000)
        print("   URL final:", pg.url)
        if "email_verification" in pg.url:
            print("   >>> ENVIADA. Falta o Matheus clicar no link de verificacao no e-mail.")
        elif "thank" in pg.url or "confirm" in pg.url:
            print("   >>> ENVIADA e confirmada.")
        else:
            print("   >>> VERIFICAR MANUALMENTE, url inesperada.")
        pg.screenshot(path=os.path.join(BASE, "_tmp", f"enviado-{slug}.png"))
    else:
        print("\n[8] DRY-RUN: nada enviado. Use --submit.")

    ctx.close()
    b.close()
