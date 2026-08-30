"""Agent Careers · GEO & SEO Specialist (Ashby, campos por UUID).

  python aplicar_agent.py [--submit]

Particularidades: a cover letter e' UPLOAD de arquivo (nao textarea); o nivel de
ingles e' um grupo de radios que compartilham o mesmo name, entao a selecao tem
que ser pelo TEXTO do label; e ha 4 checkboxes de sim/nao.
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

CV = os.path.join(BASE, PERFIL["curriculos"]["web_seo"])
CARTA = os.path.join(BASE, "cover-letter-agent.pdf")
URL = "https://jobs.ashbyhq.com/Agent/5d684cff-64ee-4ed7-bbbf-838c48b8ccd1/application"
DO_SUBMIT = "--submit" in sys.argv

MD = os.path.join(BASE, "respostas-agent-careers.md")


def bloco(titulo):
    """Extrai o corpo de um bloco delimitado por linhas de '=' no .md."""
    txt = open(MD, encoding="utf-8").read()
    partes = re.split(r"={20,}\n", txt)
    for i, p in enumerate(partes):
        if p.strip().lower().startswith(titulo.lower()):
            corpo = partes[i + 1] if i + 1 < len(partes) else ""
            return corpo.split("---\nNOTA")[0].split("--- NOTA")[0].strip()
    raise SystemExit(f"ERRO: bloco '{titulo}' nao encontrado em {MD}")


CAMPOS = {
    "_systemfield_name": ID["nome_completo"],
    "_systemfield_email": ID["email"],
    "958b6584-fdb2-4fcc-8dd7-3a80e6da9708": ID["telefone_formatado"],          # Phone/WhatsApp
    "c315b434-3c4a-4049-99b4-53d27be80236": ID["linkedin_url"],                # LinkedIn
    "9b0db257-300b-4675-9823-4ea01238231a": "%s, %s (%s)" % (
        ID["cidade"], ID["pais"], ID["fuso"]),                                 # location
    "cbbcee2d-c6b8-4e2f-8f77-f96d725e6d47": do_perfil(
        "expected_salary_usd_month"),                                          # salary USD
    "1a06e2ff-a102-4444-a70f-b71d908e4c88": bloco("150-word overview"),        # overview
    "e94e86f2-0b66-49ab-b8b1-aa62b94b88b6": bloco("JSON-LD Schema Snippet"),   # schema
}

CHECKBOXES = {
    "a5d08ac9-c52e-4d9a-90ef-33151d2a63cd": "US timezone",
    "f23cd443-fdb2-4322-afef-8078a96f826d": "independent contractor",
    "2bf9a7ca-f8ec-440d-9daa-133ba8243ea0": "JSON-LD proprio",
    "bfcd1d71-ffff-4c82-bab4-170b492b9688": "3+ anos technical SEO",
}

with sync_playwright() as p:
    b = p.chromium.launch(headless=True, channel="msedge")
    ctx = b.new_context(viewport={"width": 1400, "height": 1100}, locale="en-US")
    pg = ctx.new_page()
    print("[1]", URL)
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(4500)

    print("[2] campos (clique + fill + Tab: o fill puro nao commita no React do Ashby)")
    for nome, valor in CAMPOS.items():
        try:
            el = pg.locator(f'[name="{nome}"]').first
            el.scroll_into_view_if_needed()
            el.click()
            el.fill(str(valor))
            el.press("Tab")          # blur: e' o que faz o React aceitar o valor
            pg.wait_for_timeout(350)
            print(f"   ok  {nome[:12]}: {str(valor)[:52].replace(chr(10), ' ')}"
                  f"{'  (' + str(len(str(valor))) + ' chars)' if len(str(valor)) > 52 else ''}")
        except Exception as e:
            print(f"   ERRO {nome[:12]}: {repr(e)[:55]}")

    print("[3] nivel de ingles = Professional (clique confiavel no label)")
    try:
        pg.get_by_text("Professional", exact=True).first.click()
        pg.wait_for_timeout(400)
        print("   clicado")
    except Exception as e:
        print("   ERRO:", repr(e)[:60])

    print("[4] sim/nao (sao BOTOES Yes/No, nao checkbox)")
    # cada pergunta tem um par de botoes Yes/No; clicar o Yes dentro do bloco da pergunta
    perguntas = ["US timezone", "independent contractor",
                 "custom JSON-LD schema markup", "3+ years of dedicated professional"]
    for frag in perguntas:
        r = pg.evaluate("""(frag) => {
            const lab = [...document.querySelectorAll('label, div')]
              .find(e => e.innerText && e.innerText.includes(frag) && e.innerText.length < 400);
            if (!lab) return 'pergunta nao achada';
            let bloco = lab.closest('div');
            for (let i = 0; i < 4 && bloco; i++) {
              const yes = [...bloco.querySelectorAll('button, label, span')]
                .find(x => x.innerText.trim() === 'Yes');
              if (yes) { yes.click(); return 'clicou Yes'; }
              bloco = bloco.parentElement;
            }
            return 'botao Yes nao achado';
          }""", frag)
        print(f"   {frag[:34]}: {r}")
        pg.wait_for_timeout(350)

    print("[5] arquivos")
    finputs = pg.locator("input[type=file]")
    donos = pg.evaluate("""() => [...document.querySelectorAll('input[type=file]')]
        .map((e, i) => ({i, id: e.id || '(sem id)'}))""")
    print("   file inputs:", donos)
    for d in donos:
        if "resume" in d["id"]:
            finputs.nth(d["i"]).set_input_files(CV)
            print(f"   slot {d['i']} = CV {os.path.basename(CV)}")
        elif d["id"].startswith("a2e13964"):
            finputs.nth(d["i"]).set_input_files(CARTA)
            print(f"   slot {d['i']} = carta {os.path.basename(CARTA)}")
    # os dois uploads sao assincronos e o segundo demora mais: esperar os DOIS
    vistos = []
    for i in range(20):
        pg.wait_for_timeout(2000)
        vistos = pg.evaluate("""() => [...document.querySelectorAll('*')]
              .filter(e => e.children.length === 0 && /\\.pdf$/i.test((e.innerText||'').trim()))
              .map(e => e.innerText.trim())""")
        if len(set(vistos)) >= 2:
            print(f"   dois arquivos confirmados em {2*(i+1)}s: {sorted(set(vistos))}")
            break
    else:
        print(f"   ATENCAO: so apareceu {sorted(set(vistos))}")

    print("\n[5.5] VERIFICACAO antes de enviar (le o valor de volta)")
    faltando = []
    for nome, valor in CAMPOS.items():
        lido = pg.evaluate("""(n) => { const e = document.querySelector(`[name="${n}"]`);
                                       return e ? (e.value || '') : '(ausente)'; }""", nome)
        ok = len(lido.strip()) > 0
        if not ok:
            faltando.append(nome)
        print(f"   {'ok ' if ok else 'VAZIO'} {nome[:12]}: {len(lido)} chars")
    if faltando:
        print(f"   >>> {len(faltando)} campo(s) vazio(s) no DOM. Nao envio assim.")

    pg.screenshot(path=os.path.join(BASE, "_tmp", "agent-preenchido.png"), full_page=True)

    if DO_SUBMIT and faltando:
        print("\n[6] ABORTADO: campos vazios acima. Corrigir antes de enviar.")
    elif DO_SUBMIT:
        print("\n[6] ENVIANDO")
        bt = pg.locator("button:has-text('Submit Application')").first
        bt.scroll_into_view_if_needed()
        pg.wait_for_timeout(1200)
        bt.click()
        for i in range(12):
            pg.wait_for_timeout(3000)
            corpo = pg.inner_text("body")
            spam = re.search(r"flagged as possible spam|couldn.t submit your application", corpo, re.I)
            ok = re.search(r"thank you for applying|application (was )?(submitted|received)", corpo, re.I)
            erro = [l.strip() for l in corpo.split("\n")
                    if re.search(r"is required|please (fill|complete|enter)|invalid", l, re.I)]
            print(f"   t={3*(i+1):>2}s sucesso={bool(ok)} SPAM={bool(spam)} erros={erro[:2]}")
            if ok or spam:
                break
        print("   URL:", pg.url)
        pg.screenshot(path=os.path.join(BASE, "_tmp", "agent-enviado.png"), full_page=True)
    else:
        print("\n[6] DRY-RUN: nada enviado.")

    ctx.close()
    b.close()
