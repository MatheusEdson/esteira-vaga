"""Contractor Liberty · Professional Meta Ads Media Buyer (form GoHighLevel/LeadConnector).

  python aplicar_contractorliberty.py            # dry-run, nada enviado
  python aplicar_contractorliberty.py --submit    # envia

Regras: nada aqui afirma o que nao esta no perfil.json.
  Go High Level = Some experience (~1 ano em agencia, confirmado por ele em 18/08)
  Image/Video editing = Some experience (dirige producao, nao e editor)
  Salario = respostas_padrao.expected_salary_usd_month do perfil
"""
import sys, os, re, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.bootstrap import PERFIL, ID, do_perfil, bloco, tmp, sync_playwright



AN = PERFIL["anexos"]

URL = "https://info.contractorliberty.co/media-buyer-application"
SUBMIT = "--submit" in sys.argv
JANELA = "--janela" in sys.argv

TEXTOS = {
    "first_name": ID["first_name"],
    "last_name":  ID["last_name"],
    "city":       ID["cidade"],
    "email":      ID["email"],
    "phone":      ID["telefone_formatado"],
}
PAIS = "Brazil"
SALARIO = do_perfil("expected_salary_usd_month")

# escolha por texto de opcao (a pergunta e unica, a opcao tambem)
ESCOLHAS_DIRETAS = [
    "5 - I can fully read, write, and speak in English",
    "Yes, I can work during the weekends",
    "Yes, I can work in American timezones",
    "3 years +",
]

# Os 8 blocos de plataforma. O form e GoHighLevel: o radio nao tem `name`, e o `id` vem como
# "<opcao>_<grupo>_<indice>_<formId>". Entao a chave do grupo e o 2o segmento do id.
# Ordem de DOM confirmada em 18/08 por _tmp/diag_cl_texto.py contra a lista de campos obrigatorios.
PLATAFORMAS = [
    ("eLjBEUaLwyoiOWygEohe", "Google Sheet",              "Very experienced"),
    ("Z0ciSY8oITFczfudi63V", "Go High Level",             "Some experience"),
    ("4IEXCC0hMVxH0nGocZrq", "Meta Lead Generation Ads",  "Very experienced"),
    ("HQDZDgcKaUUvr1OeBFAS", "Image editing softwares",   "Some experience"),
    ("WqSfQNxkAAQ7WJo6JDdr", "Video editing softwares",   "Some experience"),
    ("eHe8jld8IltaSwjEAGVq", "Task management softwares", "Very experienced"),
    ("CApBXxsypRjI1ZKodID8", "Slack",                     "Very experienced"),
    ("zJgovKt1kICrdLEwpULT", "Google Docs",               "Very experienced"),
]

NARRATIVA = bloco("NARRATIVA")

JS_GRUPOS = """() => {
  const NL = String.fromCharCode(10);
  const grupos = {};
  document.querySelectorAll('input[type=radio]').forEach(e => {
    const g = e.name || '(sem-name)';
    if (!grupos[g]) {
      let q = '', node = e;
      for (let i = 0; i < 12 && node; i++) {
        const linhas = (node.innerText || '').split(NL).map(s => s.trim()).filter(s =>
          s.length > 8 && !/^(no experience|some experience|very experien|yes,|no,|[1-5] -|less than|1-2 years|2-3 years|3 years)/i.test(s));
        if (linhas.length) { q = linhas[linhas.length - 1]; break; }
        node = node.parentElement;
      }
      grupos[g] = {pergunta: q.slice(0, 130), opcoes: []};
    }
    let lb = '';
    const l = document.querySelector('label[for="' + (e.id || 'x').replace(/"/g, '') + '"]');
    if (l) lb = l.innerText.trim();
    if (!lb && e.closest('label')) lb = e.closest('label').innerText.trim();
    if (!lb) lb = e.value || '';
    grupos[g].opcoes.push({id: e.id || '', lb: lb.slice(0, 70), checked: e.checked});
  });
  return grupos;
}"""


def marca_por_texto(pg, texto):
    """Clica no radio cujo label bate com `texto`. Retorna True se ficou checked."""
    return pg.evaluate("""(txt) => {
        const alvo = txt.trim().toLowerCase();
        const radios = [...document.querySelectorAll('input[type=radio]')];
        for (const r of radios) {
          let lb = '';
          const l = document.querySelector('label[for="' + (r.id||'x').replace(/"/g,'') + '"]');
          if (l) lb = l.innerText.trim();
          if (!lb && r.closest('label')) lb = r.closest('label').innerText.trim();
          if (!lb) lb = r.value || '';
          if (lb.trim().toLowerCase() === alvo) {
            if (!r.checked) { r.click(); }
            return r.checked;
          }
        }
        return 'opcao nao encontrada';
      }""", texto)


with sync_playwright() as p:
    b = p.chromium.launch(headless=not JANELA, channel="msedge",
                          )
    ctx = b.new_context(viewport={"width": 1400, "height": 1200}, locale="en-US")
    pg = ctx.new_page()
    print("[1]", URL)
    pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
    pg.wait_for_timeout(9000)

    print("\n[2] campos de texto")
    for nome, valor in TEXTOS.items():
        ok = False
        for sel in (f"input[name='{nome}']", f"input#{nome}", f"textarea[name='{nome}']"):
            try:
                el = pg.locator(sel).first
                el.wait_for(state="visible", timeout=4000)
                el.fill(valor)
                ok = True
                break
            except Exception:
                continue
        print(f"   {nome:<12} {'ok' if ok else 'NAO PREENCHIDO':<15} {valor[:44]}")

    print("\n[2a] pais (vue-multiselect)")
    # GOTCHA: #country e um input com width:0 e position:absolute, invisivel e nao clicavel.
    # Setar .value nao registra nada no estado do Vue: o form volta "Country is required" com
    # o campo mostrando Brazil. Tem que abrir o wrapper, digitar e confirmar no teclado.
    try:
        wrapper = pg.locator("div.multiselect:has(#country)").first
        wrapper.scroll_into_view_if_needed()
        wrapper.click()
        pg.wait_for_timeout(700)
        pg.keyboard.type(PAIS, delay=110)
        pg.wait_for_timeout(1400)
        opcoes = pg.evaluate("""() => [...document.querySelectorAll('.multiselect__option')]
              .map(e => (e.textContent || '').trim()).slice(0, 6)""")
        print("   opcoes visiveis:", opcoes)

        def lido():
            return pg.evaluate("""() => {
                const w = document.querySelector('div.multiselect:has(#country)')
                       || document.querySelector('div.multiselect');
                const s = w ? w.querySelector('.multiselect__single') : null;
                return s ? (s.textContent || '').trim() : ''; }""")

        # vue-multiselect so aceita Enter na opcao DESTACADA; ArrowDown destaca a primeira.
        pg.keyboard.press("ArrowDown")
        pg.wait_for_timeout(400)
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(900)

        if not lido():
            print("   ArrowDown+Enter nao pegou, clicando na opcao com o mouse")
            alvo = pg.locator("div.multiselect:has(#country) .multiselect__option",
                              has_text=PAIS).first
            alvo.click(force=True)
            pg.wait_for_timeout(900)
    except Exception as ex:
        print("   erro na interacao:", str(ex)[:130])
    escolhido = pg.evaluate("""() => {
        const w = document.querySelector('div.multiselect:has(#country)')
               || document.querySelector('div.multiselect');
        const s = w ? w.querySelector('.multiselect__single') : null;
        return s ? (s.textContent || '').trim() : '(nada selecionado)'; }""")
    print("   country selecionado =", escolhido)

    print("\n[2b] salario (campo number)")
    r = pg.evaluate("""(v) => {
        const e = document.querySelector('input[type=number]');
        if (!e) return 'ausente';
        e.focus(); e.value = v;
        e.dispatchEvent(new Event('input',  {bubbles:true}));
        e.dispatchEvent(new Event('change', {bubbles:true}));
        return e.value; }""", SALARIO)
    print("   desired monthly salary USD =", r)

    print("\n[3] escolhas diretas")
    for t in ESCOLHAS_DIRETAS:
        print(f"   {str(marca_por_texto(pg, t)):<22} <- {t[:58]}")

    print("\n[4] narrativa (textarea)")
    r = pg.evaluate("""(txt) => {
        const tas = [...document.querySelectorAll('textarea')];
        if (!tas.length) return 'ausente';
        const e = tas[0];
        e.focus(); e.value = txt;
        e.dispatchEvent(new Event('input',  {bubbles:true}));
        e.dispatchEvent(new Event('change', {bubbles:true}));
        return e.value.length; }""", NARRATIVA)
    print("   caracteres gravados:", r)

    print("\n[5] grupos de plataforma (grupo -> opcao)")
    falhou = []
    for grupo, rotulo, alvo in PLATAFORMAS:
        res = pg.evaluate("""([grupo, alvo]) => {
            // o id e "<opcao>_<grupo>_<indice>_<formId>": casa o 2o segmento
            const rs = [...document.querySelectorAll('input[type=radio]')].filter(r => {
              const p = (r.id || '').split('_');
              return p.length > 1 && p[1] === grupo;
            });
            if (!rs.length) return 'grupo ausente';
            for (const r of rs) {
              const opc = (r.id || '').split('_')[0];
              if (opc.trim().toLowerCase() === alvo.toLowerCase()) {
                if (!r.checked) r.click();
                return r.checked ? 'OK' : 'clicou e nao marcou';
              }
            }
            return 'opcao ausente: ' + rs.map(r => (r.id||'').split('_')[0]).join(' / ');
          }""", [grupo, alvo])
        if res != "OK":
            falhou.append((rotulo, res))
        print(f"   {str(res):<12} {alvo:<17} <- {rotulo}")
    if falhou:
        print("   FALHAS:", falhou)

    print("\n[6] link do Vocaroo")
    r = pg.evaluate("""(v) => {
        const cands = [...document.querySelectorAll('input[type=text]')].filter(e => {
          const bloco = (e.closest('div,li,fieldset')||{}).innerText || '';
          return /vocaroo|record/i.test(bloco) || /vocaroo/i.test(e.placeholder||'');
        });
        if (!cands.length) return 'campo nao encontrado';
        const e = cands[cands.length - 1];
        e.focus(); e.value = v;
        e.dispatchEvent(new Event('input',  {bubbles:true}));
        e.dispatchEvent(new Event('change', {bubbles:true}));
        return e.value; }""", AN["vocaroo"] if "vocaroo" in AN else "")
    print("   vocaroo =", r)

    print("\n[7] ESTADO FINAL (conferir antes de enviar)")
    estado = pg.evaluate("""() => {
        const out = [];
        document.querySelectorAll('input,textarea,select').forEach(e => {
          if (['hidden','submit','button','image'].includes(e.type)) return;
          if (e.type === 'radio' && !e.checked) return;
          let v = e.value || '';
          if (e.type === 'radio') {
            const l = document.querySelector('label[for="' + (e.id||'x').replace(/"/g,'') + '"]');
            v = (l ? l.innerText.trim() : v);
          }
          out.push(((e.name||e.id||e.tagName).slice(0,30)) + ' = ' + String(v).slice(0,72));
        });
        return out; }""")
    for l in estado:
        print("   ", l)

    vazios = [l for l in estado if l.strip().endswith("= ")]
    print("\n   campos vazios:", len(vazios))
    for l in vazios:
        print("     VAZIO:", l)

    pg.screenshot(path=tmp("cl-preenchido.png"), full_page=True)

    if JANELA:
        # Instrumentado: o clique e dele, a leitura e minha. Grava veredito num arquivo que
        # pode ser lido de fora enquanto a janela segue aberta.
        STATUS = tmp("cl-status.txt")
        rede = []

        def registra(tag, metodo_ou_status, url):
            if any(x in url for x in ("sentry", "atlassian", "cdn-cgi/rum", "challenge-platform")):
                return
            rede.append((tag, str(metodo_ou_status), url[:130]))

        pg.on("request", lambda r: registra("REQ", r.method, r.url)
              if r.method in ("POST", "PUT") else None)
        pg.on("response", lambda r: registra("RES", r.status, r.url)
              if r.request.method in ("POST", "PUT") else None)

        print("\n" + "=" * 78)
        print("JANELA ABERTA E PREENCHIDA. Role ate o fim e clique em SUBMIT.")
        print("Estou monitorando a rede. Nao feche antes de clicar.")
        print("=" * 78)

        def escreve(veredito, extra=""):
            with open(STATUS, "w", encoding="utf-8") as f:
                f.write("hora: %s\n" % time.strftime("%H:%M:%S"))
                f.write("veredito: %s\n" % veredito)
                if extra:
                    f.write("%s\n" % extra)
                f.write("\n--- rede POST/PUT relevante ---\n")
                for t in rede:
                    f.write("  %s %s %s\n" % t)

        escreve("AGUARDANDO O CLIQUE DELE")
        enviado = False
        while len(ctx.pages) > 0:
            time.sleep(4)
            try:
                # O endpoint real e /surveys/submit. Um POST existir NAO e prova de nada:
                # 429 = limite de taxa, 4xx/5xx = recusa. So 2xx conta como enviado.
                respostas = [t for t in rede
                             if t[0] == "RES" and "surveys/submit" in t[2]]
                codigos = [t[1] for t in respostas]
                ok = [c for c in codigos if c.startswith("2")]
                corpo = pg.inner_text("body")
                msg = re.search(r"thank you|thanks|submitted|received|success|next step",
                                corpo, re.I)

                if ok and not enviado:
                    enviado = True
                    pg.screenshot(path=tmp("cl-clique-dele.png"),
                                  full_page=True)
                    escreve("ENVIADO DE VERDADE (surveys/submit %s)" % ok[-1],
                            "texto na tela: %s" % (msg.group(0) if msg else "(sem mensagem)"))
                elif codigos and not enviado:
                    detalhe = {"429": "LIMITE DE TAXA. Esperar e clicar de novo, ou trocar de IP.",
                               "403": "recusado (anti-bot ou permissao).",
                               "400": "payload rejeitado, algum campo nao agradou."}
                    escreve("RECUSADO pelo servidor: HTTP %s" % codigos[-1],
                            detalhe.get(codigos[-1], "conferir o codigo acima."))
                else:
                    escreve("AGUARDANDO O CLIQUE DELE")
            except Exception as ex:
                escreve("erro ao ler a pagina: %s" % str(ex)[:90])
    elif SUBMIT:
        print("\n[8] ENVIANDO")
        # O form roda em GoHighLevel com desafio da Cloudflare. `form-survey-event` sai com 201
        # mesmo em formulario VAZIO, entao NAO serve como prova de envio. Registro a rede para
        # achar o endpoint real de submissao e o veredito dele.
        rede = []
        pg.on("request", lambda r: rede.append(("REQ", r.method, r.url[:120]))
              if r.method in ("POST", "PUT") else None)
        pg.on("response", lambda r: rede.append(("RES", str(r.status), r.url[:120]))
              if r.request.method in ("POST", "PUT") else None)
        clicado = False
        for sel in ["button:has-text('Submit')", "button:has-text('Apply')",
                    "button[type=submit]", "input[type=submit]",
                    "button:has-text('Send')", ".ghl-btn", "button"]:
            try:
                bt = pg.locator(sel).first
                if bt.is_visible(timeout=2500):
                    bt.scroll_into_view_if_needed()
                    pg.wait_for_timeout(900)
                    print("   botao:", sel, "|", (bt.inner_text() or "")[:44])
                    bt.click()
                    clicado = True
                    break
            except Exception:
                continue
        if not clicado:
            print("   NENHUM BOTAO DE ENVIO ENCONTRADO")
        else:
            for i in range(14):
                pg.wait_for_timeout(3000)
                corpo = pg.inner_text("body")
                ok = re.search(r"thank you|thanks|submitted|received|success|next step", corpo, re.I)
                err = [l.strip() for l in corpo.split("\n")
                       if re.search(r"is required|please (fill|enter|select)|invalid", l, re.I)]
                print(f"   t={3*(i+1):>2}s sucesso={bool(ok)} erros={err[:2]}")
                if ok:
                    break
            print("   URL:", pg.url)
        print("\n   --- rede POST/PUT durante o envio ---")
        for t in rede:
            if "sentry" in t[2] or "atlassian" in t[2] or "cdn-cgi/rum" in t[2]:
                continue
            print("   ", t)
        veredito = [t for t in rede if "leadconnector" in t[2] and "survey-event" not in t[2]]
        print("\n   endpoint de submissao real:", veredito if veredito else "NENHUM (nao submeteu)")
        pg.screenshot(path=tmp("cl-enviado.png"), full_page=True)
    else:
        print("\n[8] DRY-RUN: nada enviado.")

    ctx.close()
    b.close()
