"""Adaptador inhire (*.inhire.app). Usado por Skyone e MATH Group.

  python aplicar_inhire.py skyone [--submit]
  python aplicar_inhire.py mathgroup [--submit]

O formulario tem reCAPTCHA. Se o envio for barrado, o fallback e' abrir a janela
visivel com tudo preenchido para o Matheus clicar (--janela).
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

def do_perfil(chave, secao="respostas_padrao"):
    """Le do perfil e ABORTA se estiver vazio. Ver aplicar_contractorliberty.py."""
    v = PERFIL.get(secao, {}).get(chave)
    v = str(v).strip() if v is not None else ""
    if not v:
        raise SystemExit("ERRO: preencha %s.%s no data/perfil.json" % (secao, chave))
    return v

VAGAS = {
    "skyone": ("Skyone · Especialista Growth",
               "https://skyone.inhire.app/vagas/80377c59-e5eb-4b3a-b232-6bf96e88e56c/especialista-growth",
               "paid_seo"),
    "mathgroup": ("MATH Group · Growth Specialist",
                  "https://mathgroup.inhire.app/vagas/db79801c-c690-4fdc-8360-7e3ce3da3f06/growth-specialist",
                  "paid_seo"),
    "radix": ("Radix · Fullstack Sênior (Python + React)",
              "https://radix.inhire.app/vagas/03131f7e-0e2a-4d9c-b955-5c6145f7ce51/"
              "profissional-de-desenvolvimento-fullstack-saanior-python-react?source=linkedin",
              "dev_fullstack"),
}

if len(sys.argv) < 2 or sys.argv[1] not in VAGAS:
    raise SystemExit(__doc__)
chave = sys.argv[1]
NOME, URL, CV_KEY = VAGAS[chave]
CV = os.path.join(BASE, PERFIL["curriculos"][CV_KEY])
DO_SUBMIT = "--submit" in sys.argv
JANELA = "--janela" in sys.argv


def dropdown(pg, idx, busca, alvos, rotulo):
    """react-dropdown-select: o input[name] e' opacity:0 e .fill() NAO registra
    no estado do React. Tem que clicar no wrapper, digitar no campo 'Pesquisar'
    e clicar no button[role=option][data-option-value=...].
    Retorna (ok, opcoes_vistas).
    """
    try:
        dd = pg.locator("div.react-dropdown-select").nth(idx)
        dd.scroll_into_view_if_needed()
        dd.click()
        pg.wait_for_timeout(800)
        if busca:
            pg.keyboard.type(busca, delay=120)
            pg.wait_for_timeout(2000)
        # o data-option-value do pais e' "BR", mas nas perguntas de diversidade
        # e' um UUID: casar tambem pelo ROTULO visivel do <button>.
        pares = pg.evaluate(
            """() => Array.from(document.querySelectorAll('button[role=option]'))
                 .map((e, i) => ({i: i,
                                  val: e.getAttribute('data-option-value') || '',
                                  lab: (e.getAttribute('aria-label') || e.innerText || '').trim()}))
                 .slice(0, 40)""")
        opcoes = [p["lab"] or p["val"] for p in pares]
        for alvo in alvos:
            a = alvo.lower()
            for par in pares:
                if a == par["val"].lower() or a in par["lab"].lower():
                    try:
                        pg.locator("button[role=option]").nth(par["i"]).click(timeout=2500)
                        pg.wait_for_timeout(900)
                        print(f"   [{rotulo}] escolhido: {par['lab'] or par['val']}")
                        return True, opcoes
                    except Exception:
                        continue
        print(f"   [{rotulo}] NENHUM alvo casou. opcoes: {opcoes[:14]}")
        pg.keyboard.press("Escape")
        return False, opcoes
    except Exception as e:
        print(f"   [{rotulo}] FALHOU: {repr(e)[:70]}")
        return False, []

with sync_playwright() as p:
    b = p.chromium.launch(headless=not JANELA, channel="msedge")
    ctx = b.new_context(viewport={"width": 1400, "height": 1050}, locale="pt-BR")
    pg = ctx.new_page()
    print(f"[1] {NOME}\n    {URL}")
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(4000)
    for sel in ["button:has-text('Aceitar')", "button:has-text('Accept')", "button:has-text('OK')"]:
        try:
            bt = pg.locator(sel).first
            if bt.is_visible(timeout=1500):
                bt.click(); pg.wait_for_timeout(800); break
        except Exception:
            pass
    # abrir o form se estiver atras de um botao
    for sel in ["button:has-text('Candidatar')", "a:has-text('Candidatar')",
                "button:has-text('Apply')"]:
        try:
            bt = pg.locator(sel).first
            if bt.is_visible(timeout=2000):
                bt.click(); pg.wait_for_timeout(3000); break
        except Exception:
            pass

    print("[2] campos de texto")
    campos = {
        "name": ID["nome_completo"],
        "document.value": ID["cpf"],
        "email": ID["email"],
        "phone": ID.get("telefone_e164", "").lstrip("+"),
        "linkedinUsername": ID["linkedin_url"],
        "district": ID["cidade"],
    }
    for nome, valor in campos.items():
        ok = False
        # prefixar com input/textarea: [name=...] sozinho pega wrapper que nao e' campo
        for sel in (f"input[name='{nome}']", f"textarea[name='{nome}']", f"[name='{nome}']"):
            try:
                el = pg.locator(sel).first
                el.wait_for(state="visible", timeout=6000)
                el.fill(valor)
                ok = True
                break
            except Exception:
                continue
        mostra = valor if nome != "document.value" else valor[:3] + "..."
        print(f"   {nome}: {mostra if ok else 'NAO PREENCHIDO'}")

    # GOTCHA: salaryExpectation tem mascara de moeda. fill('15000') vira "R$ 15,00"
    # (le digito a digito como centavos). Tem que digitar com press_sequentially.
    print("[2a] salario (campo com mascara de moeda)")
    try:
        sal = pg.locator("input[name='salaryExpectation']").first
        if sal.count():
            sal.fill("")
            pg.wait_for_timeout(300)
            sal.press_sequentially(str(PERFIL["identidade"]["pretensao_brl_pj"]), delay=60)
            pg.wait_for_timeout(600)
            print("   salaryExpectation =", sal.input_value())
        else:
            print("   salaryExpectation: ausente")
    except Exception as e:
        print("   salario FALHOU:", repr(e)[:60])

    def idx_dropdown(texto):
        """Indice do react-dropdown-select cujo texto visivel casa."""
        return pg.evaluate("""(t) => {
          const l = Array.from(document.querySelectorAll('div.react-dropdown-select'));
          return l.findIndex(e => (e.innerText||'').toLowerCase().includes(t.toLowerCase())
                                  && e.getBoundingClientRect().height > 0); }""", texto)

    print("[2b] pais (react-dropdown-select)")
    i_pais = idx_dropdown("País")
    if i_pais < 0:
        i_pais = idx_dropdown("Selecione seu país")
    if i_pais < 0:
        i_pais = 1
    # data-option-value do pais e' o codigo ISO ("BR"), nao o rotulo "Brasil (BR)"
    dropdown(pg, i_pais, "Bras", ["BR", "Brasil (BR)", "Brasil"], "pais")

    # o campo de cidade so habilita DEPOIS de escolher o pais
    print("[2b2] cidade (react-dropdown-select; a opcao vem como 'Cidade - UF')")
    i_cid = idx_dropdown("Informe sua cidade")
    if i_cid < 0:
        i_cid = i_pais + 1
    dropdown(pg, i_cid, ID["cidade"][:5],
             [f"{ID['cidade']} - {ID['estado']}", ID["cidade"]], "cidade")

    # GOTCHA: o checkbox de consentimento e' opacity:0 e 0x0 dentro de um <label>.
    # check() normal da timeout; dispatch_event('click') aciona o onChange do React.
    print("[2c] consentimento (privacyPolicy)")
    try:
        cb = pg.locator("input[type=checkbox][name='privacyPolicy']").first
        if cb.count():
            try:
                cb.check(force=True, timeout=4000)
            except Exception:
                pass
            if not cb.is_checked():
                cb.dispatch_event("click")
                pg.wait_for_timeout(500)
            print("   privacyPolicy =", cb.is_checked())
        else:
            print("   privacyPolicy: ausente")
    except Exception as e:
        print("   privacyPolicy FALHOU:", repr(e)[:60])

    print("[3] radios")
    # contractType = PJ ; workModel = true (aceita o modelo) ; isIndication = false
    for nome, valor in (("contractType", "PJ"), ("workModel", "true"), ("isIndication", "false")):
        r = pg.evaluate("""([n, v]) => { const e = document.querySelector(
              `input[type=radio][name="${n}"][value="${v}"]`);
            if (!e) return 'ausente'; if (!e.checked) e.click(); return e.checked; }""", [nome, valor])
        print(f"   {nome} = {valor}: {r}")

    print("[4] curriculo")
    try:
        pg.locator("input[type=file]").first.set_input_files(CV)
        pg.wait_for_timeout(5000)
        print("   ", os.path.basename(CV))
    except Exception as e:
        print("   FALHOU:", repr(e)[:60])

    # ETAPA 2 - Diversidade. O form valida as DUAS etapas juntas: enquanto as
    # perguntas de diversidade estiverem vazias, o botao 'Avancar' fica disabled.
    # perfil.json NAO tem dado demografico (raca, genero, orientacao, deficiencia),
    # entao a unica resposta legitima e' a que NAO afirma nada.
    NAO_ASSERTIVAS = ["Prefiro não responder", "Prefiro não informar",
                      "Prefiro nao responder", "Não informar", "Prefiro não dizer"]

    bloqueios = []

    def marcar_grupo():
        """Checkbox 'Prefiro nao responder' da pergunta 'Voce pertence a um dos
        grupos abaixo?'. Ela gate o botao Avancar mesmo estando na etapa 2."""
        try:
            cbs = pg.locator("input[type=checkbox]")
            for i in range(cbs.count()):
                lab = pg.evaluate("""(i) => { const e = document.querySelectorAll('input[type=checkbox]')[i];
                    const l = e.closest('label'); return l ? (l.innerText||'').trim() : ''; }""", i)
                if any(n.lower() in lab.lower() for n in NAO_ASSERTIVAS):
                    el = cbs.nth(i)
                    if el.is_checked():
                        return
                    try:
                        el.check(force=True, timeout=2500)
                    except Exception:
                        el.dispatch_event("click")
                    pg.wait_for_timeout(400)
                    print(f"   grupo: marcado '{lab[:40]}' = {el.is_checked()}")
                    return
        except Exception as e:
            print("   checkbox diversidade falhou:", repr(e)[:60])

    def resolver_dropdowns_diversidade():
        """Cada pergunta demografica que ainda estiver com placeholder.
        Captura o ENUNCIADO real (o placeholder e' sempre 'Selecione uma...')."""
        for _ in range(8):
            alvos = pg.evaluate("""() => Array.from(document.querySelectorAll('div.react-dropdown-select'))
              .map((e,i) => {
                // enunciado: subir no DOM e pegar o texto que sobra sem o do proprio select
                let p = e.parentElement, enun = '';
                for (let k = 0; k < 4 && p; k++, p = p.parentElement) {
                  const t = (p.innerText || '').replace(e.innerText || '', '').replace(/\\s+/g, ' ').trim();
                  if (t.length > 8) { enun = t; break; }
                }
                return {i: i, txt: (e.innerText||'').replace(/\\s+/g,' ').trim(), enunciado: enun.slice(0, 130),
                        vis: e.getBoundingClientRect().height > 0,
                        pulado: e.getAttribute('data-pulado') === '1'};
              })
              .filter(o => o.vis && !o.pulado && /Selecione uma/i.test(o.txt))""")
            if not alvos:
                return
            o = alvos[0]
            enun = o["enunciado"] or o["txt"]
            # Opt-in de cota PcD: e' ELEICAO sobre esta candidatura, nao afirmacao
            # sobre a pessoa. perfil.json nao declara deficiencia e a pergunta de
            # grupo ja foi respondida com 'Prefiro nao responder', entao nao pedir
            # a cota e' a resposta coerente. Fica registrado no relatorio.
            alvos_q = list(NAO_ASSERTIVAS)
            if re.search(r"defici[eê]ncia", enun, re.I):
                alvos_q = NAO_ASSERTIVAS + ["Não"]
            ok, opcoes = dropdown(pg, o["i"], "", alvos_q, f"diversidade #{o['i']}")
            print(f"      enunciado: {enun[:110]}")
            pg.evaluate("""(i) => { const e = document.querySelectorAll('div.react-dropdown-select')[i];
                if (e) e.setAttribute('data-pulado','1'); }""", o["i"])
            if not ok:
                bloqueios.append({"pergunta": enun[:110], "opcoes": opcoes})

    print("[4c] etapa 2 - diversidade (so respostas que nao afirmam nada)")
    marcar_grupo()
    resolver_dropdowns_diversidade()

    try:
        av = pg.locator("button:has-text('Avançar')").first
        if av.count():
            print("   Avancar disabled =", av.is_disabled())
            if not av.is_disabled():
                av.click(timeout=6000)
                pg.wait_for_timeout(3000)
                print("   -> avancou para a etapa 2")
                # na etapa 2 as demais perguntas demograficas ficam visiveis
                marcar_grupo()
                resolver_dropdowns_diversidade()
    except Exception as e:
        print("   Avancar falhou:", repr(e)[:60])

    if bloqueios:
        print("   !! BLOQUEIO: pergunta obrigatoria sem opcao que dispense afirmacao.")
        for blq in bloqueios:          # nao usar 'b': e' o handle do browser
            print("      pergunta:", blq["pergunta"])
            print("      opcoes  :", blq["opcoes"][:14])

    print("[4d] perguntas da etapa 2 e o que ficou respondido")
    for l in pg.evaluate("""() => Array.from(document.querySelectorAll('div.react-dropdown-select'))
      .map((e,i) => ({i:i, vis: e.getBoundingClientRect().height>0,
                      txt: (e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,70)}))
      .filter(o => o.vis).map(o => `#${o.i} ${o.txt}`)"""):
        print("   ", l)

    print("[4b] ESTADO FINAL dos campos (conferir antes de enviar)")
    estado = pg.evaluate("""() => {
      const out = [];
      document.querySelectorAll('input, textarea, select').forEach(e => {
        if (e.type === 'hidden') return;
        if (e.name && e.name.startsWith('questionsDiversity')) return;
        if (/^[\\\\0-9a-f]+$/.test(e.name || '') && e.type === 'checkbox') return;
        let v = e.type === 'checkbox' || e.type === 'radio' ? String(e.checked)
                                                            : (e.value || '').slice(0, 46);
        out.push(`${(e.name || e.type).slice(0, 24)} = ${v}`);
      });
      return out;
    }""")
    for l in estado:
        print("   ", l)

    slug = chave
    pg.screenshot(path=os.path.join(BASE, "_tmp", f"inhire-{slug}.png"), full_page=True)

    if JANELA:
        print("\n" + "=" * 74)
        print("Janela aberta e preenchida. Confira, resolva o captcha se aparecer e envie.")
        print("=" * 74)
        while len(ctx.pages) > 0:
            time.sleep(5)
    elif DO_SUBMIT:
        if bloqueios:
            raise SystemExit("   ABORTADO: pergunta obrigatoria sem resposta verdadeira "
                             "no perfil.json. Vai para fila.md, nao enviar.")
        print("\n[5] ENVIANDO")
        # o header tem um 'Candidatar' de navegacao: mirar o botao do FORM
        bt = None
        for sel in ("button:has-text('Candidatar-se para a vaga')",
                    "button[type=submit]", "button:has-text('Enviar')"):
            cand = pg.locator(sel).last
            if cand.count() and not cand.is_disabled():
                bt = cand
                print("   botao:", sel)
                break
        if bt is None:
            raise SystemExit("   ABORTADO: nenhum botao de envio habilitado.")
        bt.scroll_into_view_if_needed()
        pg.wait_for_timeout(1000)
        bt.click()
        for i in range(10):
            pg.wait_for_timeout(3000)
            corpo = pg.inner_text("body")
            ok = re.search(r"obrigad|sucesso|recebemos|thank you|candidatura enviada|success", corpo, re.I)
            erro = [l.strip() for l in corpo.split("\n")
                    if re.search(r"obrigat|inv[aá]lid|erro|required|captcha", l, re.I)]
            print(f"   t={3*(i+1):>2}s sucesso={bool(ok)} erros={erro[:3]}")
            if ok:
                break
        print("   URL:", pg.url)
        pg.screenshot(path=os.path.join(BASE, "_tmp", f"inhire-{slug}-enviado.png"), full_page=True)
    else:
        print("\n[5] DRY-RUN: nada enviado.")

    if not JANELA:
        ctx.close()
        b.close()
