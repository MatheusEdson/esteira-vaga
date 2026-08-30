"""Adaptador Greenhouse (job-boards.greenhouse.io).

  python aplicar_greenhouse.py nortal [--submit]
  python aplicar_greenhouse.py justmarkets [--submit]

Respostas de anos de experiencia definidas VAGA A VAGA abaixo, honestas.
Se aparecer combobox obrigatorio sem resposta mapeada, ABORTA sem enviar.
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
RESP = PERFIL["respostas_padrao"]
CIDADE_UF = "%s, %s" % (ID["cidade"], ID["estado"])

VAGAS = {
    "nortal": {
        "url": "https://job-boards.greenhouse.io/nortal/jobs/5198568007",
        "cv": "web_seo",
        "combos": {
            # pergunta (regex) -> opcao exata
            r"^country": ("Brazil", True),
            r"english level": "C1: Advanced.",
            r"country do you reside": "Brazil",
            # 3 anos de agencia, mas B2B SaaS/enterprise NAO e' o campo dele: nao inflar
            r"seo \(b2b saas or enterprise": "1+ Years of experience.",
            r"on-page and technical seo fundamentals": "3+ Years of experience.",
            # GEO/AIO virou disciplina em 2026; o trabalho dele e' de meses, nao de anos
            r"aio/geo principles": "Less than 1 year of experience.",
            r"seo tools": "3+ Years of experience.",
            r"translating seo and aio findings": "3+ Years of experience.",
            r"how did you hear": "Linkedin",
        },
        "textos": {r"linkedin profile": ID["linkedin_url"]},
    },
    "wellhub": {
        "url": "https://job-boards.greenhouse.io/gympass/jobs/8619348002",
        "cv": "dev_fullstack",
        "combos": {
            r"^country\*?$": ("Brazil", True),
            r"location \(city\)": (CIDADE_UF, True),
            r"country phone code": "BRA (+55)",
            r"english proficiency": "Advanced",
            r"citizen or permanent resident": "Yes",
            r"how did you hear": ("LinkedIn", True),
            r"hands-on experience with gtm orchestration":
                "Hands-on experience building multi-step automations",
            r"individual contributor":
                "I have experience in RevOps, Sales Ops, Marketing Ops",
        },
        "textos": {
            r"linkedin profile": ID["linkedin_url"],
            r"where are you currently working": RESP.get("empregador_atual_nome") or "",
            r"current base salary": str(RESP.get("salario_atual_brl") or ""),
            r"expected base salary": str(ID.get("pretensao_brl_pj") or ""),
            r"provide the details below":
                "I hold a stake in an independent performance marketing venture in Brazil, which I am "
                "currently transitioning out of. It is a services business with no commercial "
                "relationship with Wellhub and no contract that restricts me from taking this role. "
                "Happy to provide any further detail the team needs.",
        },
        # declaracao de conflito de interesses: marcar a opcao de atividade
        # profissional externa / empreendedorismo, que e' a situacao real dele
        "checkboxes": [("question_37183372002[]", "247092209002")],
    },
    # 20/08 - [DADOS] SENIOR DATA ENGINEER, remoto Brasil. Form em portugues.
    "stone": {
        "url": "https://job-boards.greenhouse.io/stone/jobs/7816045003",
        "cv": "dev_fullstack",
        "combos": {
            r"^(country|pa[ií]s)": ("Brazil", True),
            r"location \(city\)|cidade": (CIDADE_UF, True),
            r"how did you hear|como (voc[eê] )?(soube|conheceu|ficou sabendo)": "Linkedin",
        },
        "textos": {r"linkedin profile|perfil do linkedin": ID["linkedin_url"]},
    },
    "justmarkets": {
        "url": "https://job-boards.greenhouse.io/justmarkets/jobs/4927456101",
        "cv": "web_seo",
        # autocomplete de cidade: digitar e aceitar a primeira sugestao
        "combos": {r"^country": ("Brazil", True),
                   r"location \(city\)": (CIDADE_UF, True)},
        "textos": {},
    },
}

if len(sys.argv) < 2 or sys.argv[1] not in VAGAS:
    raise SystemExit(__doc__)
chave = sys.argv[1]
V = VAGAS[chave]
DO_SUBMIT = "--submit" in sys.argv
CV = os.path.join(BASE, PERFIL["curriculos"][V["cv"]])


def combo(pg, input_id, valor, primeira=False):
    """Greenhouse combobox. O clique TEM que ser do Playwright: click via JS nao
    dispara evento confiavel e o React descarta a selecao em silencio, deixando o
    form parecer preenchido e falhar na validacao."""
    # seletor por ATRIBUTO: alguns ids do Greenhouse tem colchetes
    # (ex: question_37183370002[]) e quebram o seletor CSS "#id"
    el = pg.locator(f'[id="{input_id}"]')
    el.scroll_into_view_if_needed()
    el.click()
    pg.wait_for_timeout(700)
    el.fill(valor[:18])
    pg.wait_for_timeout(1600)

    # selecao por TECLADO: e' o que o combobox React trata nativamente. Clicar na
    # opcao (por JS ou por mouse) deixa o form parecer preenchido e falhar na validacao.
    ctrl = el.get_attribute("aria-controls") or el.get_attribute("aria-owns")
    escopo = pg.locator(f'[id="{ctrl}"]') if ctrl else pg
    n = escopo.locator("[role=option]").count()
    if n == 0:
        return "(nenhuma opcao apareceu)"

    if primeira:
        pg.keyboard.press("ArrowDown")
        pg.wait_for_timeout(400)
        pg.keyboard.press("Enter")
    else:
        # desce ate a opcao cujo texto bate
        achou = False
        for i in range(min(n, 30)):
            pg.keyboard.press("ArrowDown")
            pg.wait_for_timeout(180)
            atual = pg.evaluate("""(id) => {
                const el = document.getElementById(id);
                const a = el && el.getAttribute('aria-activedescendant');
                const o = a ? document.getElementById(a) : null;
                return o ? o.innerText.trim() : '';
              }""", input_id)
            if atual == valor or atual.startswith(valor[:14]):
                achou = True
                break
        if not achou:
            return f"(nao achei '{valor}' navegando {n} opcoes)"
        pg.keyboard.press("Enter")

    pg.wait_for_timeout(900)
    # react-select: o input fica vazio DE PROPOSITO. O valor escolhido vive no
    # div.select__single-value e o container ganha a classe --has-value.
    estado = pg.evaluate("""(id) => {
        const el = document.getElementById(id);
        if (!el) return {ok: false, v: '(input sumiu)'};
        const ctrl = el.closest('.select__control') || el.closest('div');
        const sv = ctrl ? ctrl.querySelector('.select__single-value') : null;
        const has = ctrl ? ctrl.querySelector('.select__value-container--has-value') : null;
        return {ok: !!(sv || has), v: sv ? sv.innerText.trim() : (el.value || '')};
      }""", input_id)
    return True if estado["ok"] else f"(nada selecionado: {estado['v']})"


with sync_playwright() as p:
    b = p.chromium.launch(headless=True, channel="msedge")
    ctx = b.new_context(viewport={"width": 1400, "height": 1100}, locale="en-US")
    pg = ctx.new_page()
    print(f"[1] {chave}: {V['url']}")
    pg.goto(V["url"], wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(4000)

    print("[2] dados pessoais")

    def preencher(campo, valor):
        """Greenhouse usa id em alguns campos e name em outros."""
        for sel in (f'[id="{campo}"]', f"input[name='{campo}']"):
            try:
                el = pg.locator(sel).first
                el.wait_for(state="visible", timeout=6000)
                el.fill(valor)
                return True
            except Exception:
                continue
        print(f"   {campo}: NAO ENCONTRADO")
        return False

    for campo, valor in (("first_name", ID["first_name"]), ("last_name", ID["last_name"]),
                         ("email", ID["email"]), ("phone", ID.get("telefone_e164", "").lstrip("+"))):
        preencher(campo, valor)
    print("   nome, email, telefone")

    print("[3] curriculo")
    pg.locator("input[type=file]").first.set_input_files(CV)
    pg.wait_for_timeout(6000)
    print("   ", os.path.basename(CV), "| pdf na pagina:",
          pg.evaluate("() => /\\.pdf/i.test(document.body.innerText)"))

    print("[4] comboboxes")
    campos = pg.evaluate("""() => [...document.querySelectorAll('input[role=combobox]')]
        .map(e => ({id: e.id || '',
                    lab: (document.querySelector(`label[for="${CSS.escape(e.id)}"]`)||{innerText:''})
                          .innerText.trim().slice(0,120)}))
        .filter(c => c.id && c.lab)""")
    bloqueios = []
    for c in campos:
        lab = c["lab"].lower()
        if lab.startswith("search"):     # seletor de pais DO TELEFONE, nao e' campo do form
            continue
        alvo = next((v for k, v in V["combos"].items() if re.search(k, lab)), None)
        if not alvo:
            obrig = "*" in c["lab"]
            print(f"   [{'REQ SEM RESPOSTA' if obrig else 'opcional'}] {c['lab'][:70]}")
            if obrig:
                bloqueios.append(c["lab"])
            continue
        # alvo pode ser "texto" ou ("texto", usar_primeira_sugestao)
        primeira = False
        if isinstance(alvo, tuple):
            alvo, primeira = alvo
        r = combo(pg, c["id"], alvo, primeira)
        print(f"   [{'ok' if r is True else 'FALHOU'}] {c['lab'][:56]} -> {alvo}"
              + ("" if r is True else f" | {r}"))
        if r is not True:
            bloqueios.append(c["lab"])

    for nome, valor in V.get("checkboxes", []):
        r = pg.evaluate("""([n, v]) => { const e = document.querySelector(
              `input[type=checkbox][name="${n}"][value="${v}"]`);
            if (!e) return 'ausente'; if (!e.checked) e.click(); return e.checked; }""",
            [nome, valor])
        print(f"   [checkbox] {nome} = {valor}: {r}")

    print("[5] textos extras")
    for padrao, valor in V["textos"].items():
        achou = pg.evaluate("""(padrao) => {
            const rx = new RegExp(padrao, 'i');
            // inclui textarea: o campo de detalhe do conflito de interesses e' textarea,
            // e procurar so' em input[type=text] deixava ele vazio e travava o envio
            for (const e of document.querySelectorAll('input[type=text], textarea')) {
              const l = document.querySelector(`label[for="${CSS.escape(e.id||'')}"]`);
              if (l && rx.test(l.innerText)) return e.id || e.name;
            }
            return '';
          }""", padrao)
        if achou:
            preencher(achou, valor)
            print(f"   {padrao} -> {valor}")
        else:
            print(f"   {padrao}: campo nao encontrado")

    if bloqueios:
        print("\n" + "=" * 74)
        print("ABORTADO SEM ENVIAR. Campo obrigatorio sem resposta:")
        for x in bloqueios:
            print("  *", x[:100])
        print("=" * 74)
        ctx.close(); b.close(); raise SystemExit(2)

    pg.screenshot(path=os.path.join(BASE, "_tmp", f"gh-{chave}-preenchido.png"), full_page=True)

    if DO_SUBMIT:
        print("\n[6] ENVIANDO")
        bt = pg.locator("button:has-text('Submit application'), button[type=submit]").first
        bt.scroll_into_view_if_needed()
        pg.wait_for_timeout(1000)

        # 1o clique: o Greenhouse dispara um codigo de 8 caracteres para o e-mail
        bt.click()
        pg.wait_for_timeout(6000)

        # O codigo nao da' para automatizar: espera o Matheus colar num arquivo.
        precisa_codigo = "verification code was sent" in pg.inner_text("body").lower()
        if precisa_codigo:
            arq = os.path.join(BASE, "_tmp", f"codigo-{chave}.txt")
            if os.path.exists(arq):
                os.remove(arq)
            print("\n" + "=" * 74)
            print("CODIGO NECESSARIO. O Greenhouse mandou 8 caracteres para")
            print(f"  {ID['email']}")
            print(f"Escreva o codigo em: {arq}")
            print("Vou checar a cada 5s por ate 12 minutos.")
            print("=" * 74)
            codigo = None
            for _ in range(144):
                pg.wait_for_timeout(5000)
                if os.path.exists(arq):
                    # utf-8-sig: o Set-Content do PowerShell 5.1 grava BOM, e o BOM
                    # ocupa a primeira caixinha do OTP e empurra o codigo inteiro
                    c = open(arq, encoding="utf-8-sig").read().strip().lstrip("﻿")
                    if len(c) >= 6:
                        codigo = c
                        break
            if not codigo:
                print("   nao recebi o codigo a tempo. Nada foi enviado.")
                pg.screenshot(path=os.path.join(BASE, "_tmp", f"gh-{chave}-esperando.png"), full_page=True)
                ctx.close(); b.close(); raise SystemExit(3)
            print(f"   codigo recebido: {codigo}")
            # widget de OTP: preencher caixa a caixa nao registra no React. Focar a
            # primeira e DIGITAR, que o proprio widget avanca sozinho.
            primeira_caixa = None
            for sel in ["input[maxlength='1']", "input[autocomplete='one-time-code']",
                        "input[inputmode='text']", "input[type='text']"]:
                loc = pg.locator(sel)
                if loc.count() >= 6:
                    primeira_caixa = loc.first
                    print(f"   caixas encontradas por '{sel}': {loc.count()}")
                    break
            if primeira_caixa is None:
                print("   NAO achei as caixas do codigo")
            else:
                primeira_caixa.click()
                pg.wait_for_timeout(400)
                pg.keyboard.type(codigo, delay=180)
                pg.wait_for_timeout(2000)

            bt = pg.locator("button:has-text('Submit application'), button[type=submit]").first
            bt.scroll_into_view_if_needed()
            for _ in range(20):   # esperar o botao habilitar
                if not bt.is_disabled():
                    break
                pg.wait_for_timeout(1000)
            print("   botao habilitado:", not bt.is_disabled())
            if bt.is_disabled():
                pg.screenshot(path=os.path.join(BASE, "_tmp", f"gh-{chave}-codigo.png"), full_page=True)
                print("   codigo nao habilitou o envio. Screenshot salvo.")
                ctx.close(); b.close(); raise SystemExit(4)

        bt.click()
        for i in range(10):
            pg.wait_for_timeout(3000)
            corpo = pg.inner_text("body")
            ok = re.search(r"thank you|application (was )?(submitted|received)|successfully", corpo, re.I)
            erro = [l.strip() for l in corpo.split("\n")
                    if re.search(r"is required|please (fill|enter|select)|invalid|error", l, re.I)]
            print(f"   t={3*(i+1):>2}s sucesso={bool(ok)} erros={erro[:3]}")
            if ok:
                break
        print("   URL:", pg.url)
        pg.screenshot(path=os.path.join(BASE, "_tmp", f"gh-{chave}-enviado.png"), full_page=True)
    else:
        print("\n[6] DRY-RUN: nada enviado.")

    ctx.close()
    b.close()
