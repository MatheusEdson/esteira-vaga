"""Adaptador LinkedIn Easy Apply ("Candidatura simplificada"), com a sessao
persistente do Matheus.

  python aplicar_easyapply.py <job_id> [--submit]

Dry-run por padrao: abre o modal, percorre as etapas SEM enviar, imprime todos os
campos e perguntas de cada etapa e tira screenshot. O envio real so acontece com
--submit, e mesmo assim para se aparecer campo obrigatorio desconhecido.
"""
import sys, os, json, re, unicodedata
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _c in (_d, _os.path.dirname(_d)):
    if _c not in _sys.path: _sys.path.insert(0, _c)
from nav import sync_playwright   # patchright endurecido, ver nav.py


def sem_acento(s):
    """Pergunta customizada do LinkedIn as vezes recusa nao-ASCII com
    'Please enter a valid answer'. Visto na Emerging Travel Group (20/08):
    'Cidade, UF, Brasil' reprovado, 'Cidade, Brazil' aceito."""
    n = unicodedata.normalize("NFD", s)
    return "".join(c for c in n if unicodedata.category(c) != "Mn")

BASE = os.path.dirname(os.path.abspath(__file__))
from core.perfil import perfil as _carregar_perfil   # le data/perfil.json
PERFIL = _carregar_perfil()
from core.perfil import curriculo as _cv, anexo as _anexo, respostas_md as _resp
ID = PERFIL["identidade"]

if len(sys.argv) < 2:
    raise SystemExit(__doc__)
JOB = sys.argv[1]
DO_SUBMIT = "--submit" in sys.argv
URL = f"https://www.linkedin.com/jobs/view/{JOB}/"

# --cv <chave de perfil.curriculos>: sobe o CV rastreado em vez de confiar no
# 'resume.pdf' que o LinkedIn guardou (nao se sabe qual versao e').
CV = None
if "--cv" in sys.argv:
    chave = sys.argv[sys.argv.index("--cv") + 1]
    CV = _cv(chave)

# respostas verdadeiras, todas ancoradas no perfil.json
RESP = [
    # "where are you CURRENTLY located" nao casava com "where are you located":
    # a palavra no meio quebrava o padrao e bloqueava vaga com resposta no perfil.
    # Valor em ASCII e com o pais em ingles: a pergunta customizada da ETG
    # recusou "Cidade, UF, Brasil" com 'Please enter a valid answer' e
    # aceitou "Cidade, Brazil". Mesmo fato, formato que o campo aceita.
    (r"current(ly)?\s+locat|where are you\b.{0,20}\blocat|location \(city\)|"
     r"localiza|cidade|name your city|city and country",
     sem_acento(f"{ID['cidade']}, Brazil")),
    (r"first name|nome$", ID["first_name"]),
    (r"last name|sobrenome", ID["last_name"]),
    (r"linkedin", ID["linkedin_url"]),
    (r"available|start date|disponibilidade para in",
     PERFIL["respostas_padrao"]["availability_start"]),
]

# Placeholder de select nao conta como resposta: sem isto o guardrail nao dispara
# e o adaptador fica em loop clicando 'Avancar' num form que nao valida.
PLACEHOLDER = r"^\s*$|^(select an option|selecione(\s+uma)?(\s+op[cç][aã]o)?|escolha|choose)\s*$"

def eh_vazio(v):
    return not v or bool(re.match(PLACEHOLDER, v.strip(), re.I))

# Consentimento de tratamento de dados / termos: parte mecanica do ato de
# candidatar-se, que ele autorizou. Nao e' alegacao de experiencia.
CONSENT = (r"consinto|consentimento|concordo|autorizo|li e (aceito|compreendi)|"
           r"tratamento dos meus dados|privacidade|lgpd|terms|privacy|consent|agree")

# Select substantivo so e' respondido com casamento explicito no perfil.json.
# padrao da pergunta -> regex da opcao aceitavel
RESP_SELECT = [
    (r"authorized to work in brazil|autoriza[cç][aã]o para trabalhar no brasil",
     r"^(yes|sim)"),
    (r"require.*(visa|sponsorship).*(brazil|brasil)", r"^(no|n[aã]o)"),
    (r"\bfluent\b.*(english|ingl)|n[ií]vel de ingl", r"fluent|advanced|c1"),
]

DUMP = """() => {
  const modal = document.querySelector('.jobs-easy-apply-modal, [role=dialog]');
  if (!modal) return {titulo: '(sem modal)', campos: [], texto: ''};
  const campos = [];
  modal.querySelectorAll('input, textarea, select').forEach(e => {
    if (e.type === 'hidden') return;
    const lab = e.labels && e.labels[0] ? e.labels[0].innerText.trim()
              : (e.getAttribute('aria-label') || '');
    const v = (e.type === 'checkbox' || e.type === 'radio')
      ? String(e.checked) : (e.value || '');
    campos.push({
      tipo: e.tagName + '/' + (e.type || ''),
      id: e.id || '',            // NAO truncar: o id e' usado como seletor
      idcurto: (e.id || '').slice(0, 46),
      req: e.required || e.getAttribute('aria-required') === 'true',
      label: lab.replace(/\\n/g, ' ').slice(0, 110),
      val: v.slice(0, 46),
      // texto integral das opcoes: preciso para decidir consentimento vs pergunta
      opts: e.tagName === 'SELECT' ? Array.from(e.options).map(o => o.text.trim()) : []
    });
  });
  const opts = [];
  modal.querySelectorAll('select').forEach(s => {
    opts.push((s.getAttribute('aria-label')||s.id||'').slice(0,40) + ' :: '
      + Array.from(s.options).map(o => o.text).slice(0, 8).join(' / '));
  });
  return {
    titulo: (modal.querySelector('h2, h3')||{}).innerText || '',
    campos: campos, selects: opts,
    texto: (modal.innerText || '').split('\\n').map(s=>s.trim()).filter(Boolean).slice(0, 30).join(' | ')
  };
}"""

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        os.path.join(BASE, "_tmp", "edge-profile-linkedin"), channel="msedge",
        headless=True, viewport={"width": 1450, "height": 1100}, locale="en-US",
        )
    pg = ctx.new_page()
    print(f"[1] {URL}")
    # GOTCHA: ir direto na rota /apply/ e' mais confiavel que clicar no gatilho.
    # O LinkedIn redireciona de volta para /jobs/view/ E abre o modal, mas leva
    # varios segundos: sem wait_for_selector o dump acha que nao ha modal.
    pg.goto(URL.rstrip("/") + "/apply/?openSDUIApplyFlow=true",
            wait_until="domcontentloaded", timeout=70000)
    pg.wait_for_timeout(3000)

    print("[2] esperando o modal de candidatura")
    aberto = False
    try:
        pg.wait_for_selector(".jobs-easy-apply-modal, [role=dialog]", timeout=25000)
        aberto = True
    except Exception:
        # fallback: o gatilho as vezes e' <a>, as vezes <button>
        for sel in ["button:has-text('Candidatura simplificada')",
                    "a:has-text('Candidatura simplificada')",
                    "[aria-label*='candidatura simplificada' i]",
                    "button:has-text('Easy Apply')",
                    "a:has-text('Easy Apply')",
                    ".jobs-apply-button"]:
            try:
                bt = pg.locator(sel).first
                bt.scroll_into_view_if_needed()
                bt.click(timeout=6000)
                pg.wait_for_selector(".jobs-easy-apply-modal, [role=dialog]", timeout=20000)
                aberto = True
                break
            except Exception:
                continue
    print("    modal aberto:", aberto)
    if not aberto:
        raise SystemExit("    ABORTADO: modal nao abriu.")

    etapa = 0
    assinaturas = []
    while etapa < 8:
        etapa += 1
        d = pg.evaluate(DUMP)
        # Deteccao de travamento: se a etapa repete identica, 'Avancar' nao esta
        # validando e o loop estava mascarando isso como progresso.
        assin = "|".join(f"{c['label']}={c['val']}" for c in d["campos"])
        if assin and assin in assinaturas:
            print(f"\n    !! TRAVADO: a etapa {etapa} e' identica a uma anterior; "
                  f"'Avancar' nao valida. Campos visiveis estao todos preenchidos, "
                  f"logo o bloqueio e' invisivel no DOM.")
            pg.screenshot(path=os.path.join(BASE, "_tmp", f"easyapply-{JOB}-travado.png"),
                          full_page=False)
            break
        assinaturas.append(assin)
        print(f"\n--- ETAPA {etapa}: {d['titulo'][:70]} ---")
        for c in d["campos"]:
            print(f"    {c['tipo']:16s} req={str(c['req']):5s} val={c['val'][:26]:28s} | {c['label']}")
        for s in d.get("selects", []):
            print(f"    OPCOES {s[:150]}")
        if not d["campos"]:
            print("    (sem campos)", d["texto"][:200])

        # CV rastreado, quando a etapa tiver input[type=file]
        if CV and any(c["tipo"].endswith("/file") for c in d["campos"]):
            try:
                pg.locator("[role=dialog] input[type=file], "
                           ".jobs-easy-apply-modal input[type=file]").first.set_input_files(CV)
                pg.wait_for_timeout(4000)
                print(f"    CV enviado: {os.path.basename(CV)}")
            except Exception as e:
                print("    CV FALHOU:", repr(e)[:70])

        # preencher campos de texto vazios com resposta verdadeira do perfil.json
        for c in d["campos"]:
            if c["val"] or not c["tipo"].startswith("INPUT/text") or not c["id"]:
                continue
            for padrao, valor in RESP:
                if re.search(padrao, c["label"], re.I):
                    try:
                        loc = pg.locator(f'[id="{c["id"]}"]').first
                        loc.fill(valor)
                        pg.wait_for_timeout(600)
                        # Campo de autocomplete (cidade): digitar NAO registra o valor,
                        # e' preciso escolher na lista. Mesmo problema do inhire/GHL.
                        if pg.evaluate(
                                """id => { const e = document.getElementById(id); return !!e && (
                                     e.getAttribute('role') === 'combobox' ||
                                     !!e.getAttribute('aria-autocomplete') ||
                                     !!e.getAttribute('aria-controls')); }""", c["id"]):
                            try:
                                loc.press("ArrowDown"); pg.wait_for_timeout(1200)
                                opc = pg.locator("[role=option], .basic-typeahead__triggered-content "
                                                 "div[role=button]").first
                                if opc.count():
                                    esc = opc.inner_text()[:50]
                                    opc.click(timeout=3000)
                                    print(f"    typeahead: escolhi '{esc}'")
                                else:
                                    loc.press("Enter")
                            except Exception as e2:
                                print("    typeahead falhou:", repr(e2)[:50])
                        print(f"    preenchi '{c['label'][:44]}' = {valor[:40]}")
                    except Exception as e:
                        print("    falhou preencher:", repr(e)[:50])
                    break

        # SELECT obrigatorio. Duas classes, tratadas de forma diferente:
        #  (a) consentimento de dados/termos: e' ato mecanico de candidatar-se, nao
        #      afirmacao sobre experiencia. Unica opcao real -> marcar.
        #  (b) qualquer pergunta substantiva: NAO adivinhar. Cai no guardrail.
        for c in d["campos"]:
            if not c["tipo"].startswith("SELECT") or not c["id"]:
                continue
            if not eh_vazio(c["val"]):
                continue
            reais = [o for o in c["opts"] if not eh_vazio(o)]
            consent = re.search(CONSENT, c["label"], re.I) or (
                len(reais) == 1 and re.search(CONSENT, reais[0], re.I))
            if consent and len(reais) == 1:
                try:
                    pg.locator(f'[id="{c["id"]}"]').first.select_option(label=reais[0])
                    pg.wait_for_timeout(500)
                    print(f"    consentimento marcado: {reais[0][:70]}")
                except Exception as e:
                    print("    falhou marcar consentimento:", repr(e)[:60])
                continue
            # pergunta substantiva: so responde se houver casamento no perfil.json
            alvo = None
            for padrao, valor in RESP_SELECT:
                if re.search(padrao, c["label"], re.I):
                    alvo = next((o for o in reais if re.search(valor, o, re.I)), None)
                    break
            if alvo:
                try:
                    pg.locator(f'[id="{c["id"]}"]').first.select_option(label=alvo)
                    pg.wait_for_timeout(500)
                    print(f"    respondi (perfil.json) '{c['label'][:40]}' = {alvo[:40]}")
                except Exception as e:
                    print("    falhou responder select:", repr(e)[:60])

        # GUARDRAIL: campo obrigatorio que ficou vazio = sem resposta no perfil.json
        d2 = pg.evaluate(DUMP)
        faltando = [c for c in d2["campos"]
                    if c["req"] and eh_vazio(c["val"]) and c["tipo"] != "INPUT/file"]
        if faltando:
            print("\n    !! BLOQUEIO: campo obrigatorio sem resposta verdadeira no perfil.json:")
            for c in faltando:
                print(f"       - {c['label']}")
            print("    -> vai para fila.md. NAO enviando.")
            pg.screenshot(path=os.path.join(BASE, "_tmp", f"easyapply-{JOB}-bloqueio.png"),
                          full_page=False)
            break

        pg.screenshot(path=os.path.join(BASE, "_tmp", f"easyapply-{JOB}-e{etapa}.png"),
                      full_page=False)

        # botao de avancar / revisar / enviar
        rotulos = pg.evaluate("""() => {
          const m = document.querySelector('.jobs-easy-apply-modal, [role=dialog]');
          if (!m) return [];
          return Array.from(m.querySelectorAll('button'))
            .map(b => (b.innerText || b.getAttribute('aria-label') || '').trim())
            .filter(Boolean).slice(0, 10);
        }""")
        print("    botoes:", rotulos)

        eh_envio = any(re.search(r"enviar candidatura|submit application", r, re.I)
                       for r in rotulos)
        if eh_envio and not DO_SUBMIT:
            print("\n[3] DRY-RUN: cheguei na etapa de ENVIO e PAREI. Nada enviado.")
            break
        if eh_envio and DO_SUBMIT:
            print("\n[3] ENVIANDO")
            pg.locator("button:has-text('Enviar candidatura'), "
                       "button:has-text('Submit application')").first.click()
            pg.wait_for_timeout(6000)
            print("    corpo:", pg.inner_text("body")[:220].replace("\n", " | "))
            pg.screenshot(path=os.path.join(BASE, "_tmp", f"easyapply-{JOB}-enviado.png"),
                          full_page=False)
            break

        avancou = False
        for r in ("Avançar", "Next", "Revisar", "Review", "Continuar"):
            try:
                bt = pg.locator(f"button:has-text('{r}')").first
                if bt.is_visible(timeout=1500):
                    bt.click(); pg.wait_for_timeout(3000); avancou = True; break
            except Exception:
                continue
        if not avancou:
            print("    (nao achei botao de avancar; parando)")
            break

    ctx.close()
