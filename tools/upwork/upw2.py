"""Anexa no Brave que o MATHEUS abriu. Nunca lanca browser.

  python upw2.py estado
  python upw2.py ir <url>
  python upw2.py ler
  python upw2.py campos                      lista campos e botoes da tela atual
  python upw2.py set "<rotulo>" "<texto>"    preenche por rotulo (texto pode ser @arquivo.txt)
  python upw2.py clicar "<texto do botao>"   clica botao por texto
  python upw2.py propor <url-da-vaga> <arquivo-com-a-proposta>
  python upw2.py preparar [connects]   # resolve reajuste + lance, e diz o que falta

POR QUE ISTO EXISTE E O RESTO FOI DESCARTADO. Na Upwork, todo caminho em que o Playwright
LANCAVA o browser terminou em loop infinito de checkbox da Cloudflare, mesmo com patchright,
sandbox ligado, perfil envelhecido e zero instrumentacao durante o desafio. O mesmo IP, na
mesma conta e no mesmo minuto, passou de primeira num Brave limpo aberto a mao. A variavel
era quem abria o processo.

Aqui o processo e' aberto por ele (ABRIR-BRAVE.ps1, sem uma flag de automacao) e eu apenas
me anexo pela porta de debug. Cada comando conecta, faz uma coisa e desconecta: o browser
segue vivo entre comandos, entao o cf_clearance conquistado no primeiro clique vale para
todos os comandos seguintes. Era exatamente isso que o ciclo de relancamento destruia.

REGRA QUE NAO SE QUEBRA: `propor` PREENCHE e para. Nunca clica em Send. Enviar e' dele.
"""
import sys, os, io, json, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stdout.reconfigure(line_buffering=True)

from patchright.sync_api import sync_playwright

PORTA = int(os.environ.get("UPW_PORTA", "9333"))
ALVO = "http://127.0.0.1:%d" % PORTA


def bloqueado(pg):
    try:
        t = (pg.title() or "").lower()
    except Exception:
        return False
    # pt-BR incluido: o perfil do Brave esta em portugues e o interstitial vira
    # "Um momento...". Sem isso o detector jurou "sem muro" com o muro na tela.
    return any(s in t for s in ("just a moment", "um momento", "verify you are human",
                                "verifique se voc", "attention required", "atenção necess",
                                "checking your browser", "verificando seu navegador"))


def esperar_passar(pg, seg=120):
    """Espera o interstitial cair, em vez de dormir um tempo fixo.

    Espera fixa de 5s media a tela antes de o desafio terminar e reportava "muro" numa
    pagina que ia passar sozinha. Aqui a condicao e' o titulo deixar de ser interstitial;
    o tempo e' consequencia, nao chute."""
    fim = time.time() + seg
    while time.time() < fim:
        if not bloqueado(pg):
            pg.wait_for_timeout(1500)          # deixa o app pintar depois do desafio
            return True
        pg.wait_for_timeout(2000)
    return False


def aba(br, preferir="upwork.com"):
    """A aba de trabalho e' a que esta no Upwork e nao e' login. Escolher por posicao
    ja me fez reportar 'nao logado' olhando para uma about:blank do humano."""
    ctxs = br.contexts or []
    todas = [p for c in ctxs for p in c.pages]
    if not todas:
        raise SystemExit("Nenhuma aba aberta no Brave.")
    for p in todas:
        try:
            u = p.url
        except Exception:
            continue
        if preferir in u and "login" not in u and "signup" not in u:
            return p
    for p in todas:
        try:
            if preferir in p.url:
                return p
        except Exception:
            continue
    return todas[0]


JS_LER = r"""() => ({
  doc: document.title,
  h1: [...document.querySelectorAll("h1")].map(e => e.innerText.trim()).slice(0, 3),
  skills: [...new Set([...document.querySelectorAll(".air3-token,[data-test*='Skill']")]
            .map(e => e.innerText.trim()).filter(Boolean))].slice(0, 30),
  corpo: (document.body.innerText || "").slice(0, 12000)
})"""


JS_CAMPOS = r"""() => {
  const rotulo = (el) => {
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l && l.innerText.trim()) return l.innerText.trim();
    }
    const pai = el.closest("label");
    if (pai && pai.innerText.trim()) return pai.innerText.trim();
    return el.getAttribute("aria-label") || el.getAttribute("placeholder")
        || el.getAttribute("name") || el.id || "";
  };
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
  };
  const saida = [];
  document.querySelectorAll("[data-upw]").forEach(e => e.removeAttribute("data-upw"));
  document.querySelectorAll("input,textarea,select").forEach((el, i) => {
    if (el.type === "hidden" || !vis(el)) return;
    const esc = (v) => (v || "").replace(/["]/g, "");
    let sel = "";
    if (el.id) sel = el.tagName.toLowerCase() + "#" + CSS.escape(el.id);
    else if (el.getAttribute("name")) sel = el.tagName.toLowerCase() + '[name="' + esc(el.getAttribute("name")) + '"]';
    else if (el.getAttribute("aria-label")) sel = el.tagName.toLowerCase() + '[aria-label="' + esc(el.getAttribute("aria-label")) + '"]';
    else if (el.getAttribute("placeholder")) sel = el.tagName.toLowerCase() + '[placeholder="' + esc(el.getAttribute("placeholder")) + '"]';
    saida.push({
      sel: sel,
      i: saida.length,
      tag: el.tagName.toLowerCase(),
      tipo: el.type || "",
      rotulo: rotulo(el).replace(/\s+/g, " ").slice(0, 70),
      valor: (el.value || "").slice(0, 60),
      max: el.getAttribute("maxlength") || null,
      dialogo: !!el.closest("[role='dialog'],.air3-modal")
    });
  });
  const botoes = [];
  document.querySelectorAll("button,a[role='button'],[data-test*='btn']").forEach(b => {
    if (!vis(b)) return;
    const t = (b.innerText || b.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim();
    if (t && t.length < 42) botoes.push({ t, dialogo: !!b.closest("[role='dialog'],.air3-modal") });
  });
  return { campos: saida, botoes: [...new Map(botoes.map(b => [b.t, b])).values()].slice(0, 40) };
}"""


def _loc(pg, c):
    """Localiza o campo por atributo proprio dele. Ja tentei carimbar o DOM com um
    atributo meu e o React apagava na re-renderizacao seguinte."""
    if c.get("sel"):
        l = pg.locator(c["sel"])
        if l.count() == 1:
            return l
        if l.count() > 1:
            return l.first
    # ultimo recurso: posicao entre os VISIVEIS, que e' como o JS enumerou
    return pg.locator("input:not([type=hidden]):visible, textarea:visible, select:visible").nth(c["i"])


def achar_campo(pg, agulha):
    """Acha o campo por ROTULO, nao por indice. Indice muda entre uma chamada e outra
    quando um modal abre ou fecha, e escrever no campo errado do perfil e' silencioso."""
    ag = agulha.lower()
    d = pg.evaluate(JS_CAMPOS)
    alvos = [c for c in d["campos"] if ag in (c["rotulo"] or "").lower()]
    if not alvos:
        return None, d
    alvos.sort(key=lambda c: (not c["dialogo"], len(c["rotulo"])))   # modal aberto ganha
    return alvos[0], d



def erros_do_form(pg):
    """Lista os erros de validacao visiveis na tela de proposta.

    A Upwork diz "Please fix the errors below" sem apontar onde, e a mensagem especifica
    fica num no separado. Sem ler esses nos, o envio falha em silencio e voce clica de novo
    achando que foi rede."""
    achados, vistos = [], set()
    for sel in ("[class*=error]", "[role=alert]"):
        for e in pg.locator(sel).all():
            try:
                t = " ".join((e.inner_text() or "").split()).strip()
            except Exception:
                continue
            if t and len(t) > 3 and t not in vistos:
                vistos.add(t)
                achados.append(t[:110])
    return achados


def resolver_reajuste(pg, escolha="Never"):
    """Preenche o 'Schedule a rate increase', que e' OBRIGATORIO apesar de dizer optional.

    Em vaga por hora, sem escolher a frequencia o envio falha e a unica pista e'
    "Please fix the errors below". Custou cinco tentativas descobrir.

    O controle nao e' <select>: e' um combobox proprio deles (air3-dropdown) que so' abre
    com sequencia real de mouse, e que FECHA E RESETA se qualquer outra interacao acontecer
    entre abrir e escolher. Por isso abre e escolhe na mesma passagem."""
    alvo = None
    for e in pg.locator("div.air3-dropdown-toggle[role=combobox]").all():
        try:
            if "frequency" in (e.inner_text() or "").lower():
                alvo = e
                break
        except Exception:
            continue
    if alvo is None:
        return None                      # vaga de preco fixo nao tem reajuste

    alvo.click()
    pg.wait_for_timeout(1200)
    for o in pg.locator("[role=option], .air3-dropdown-menu li").all():
        try:
            if (o.inner_text() or "").strip() == escolha:
                o.click()
                pg.wait_for_timeout(1200)
                return escolha
        except Exception:
            continue
    return "nao achei a opcao %r" % escolha


def confirmar_lance(pg, connects):
    """Aplica o lance de posicao da proposta.

    Digitar o numero no campo NAO aplica nada: existe um botao 'Set bid' separado, e sem
    clicar nele a Upwork usa o valor anterior e reclama que 'your bid is set to N'.

    A Upwork so' cobra o lance se voce ficar entre os 4 primeiros, entao lance baixo e'
    opcao gratis: ou voce sobe na lista, ou nao paga nada."""
    campo = pg.locator("input[type=number]").first
    try:
        campo.fill(str(connects))
    except Exception:
        return "nao achei o campo de lance"
    for b in pg.locator("button").all():
        try:
            if (b.inner_text() or "").strip() == "Set bid":
                b.click()
                pg.wait_for_timeout(1500)
                return connects
        except Exception:
            continue
    return "campo preenchido, mas nao achei o botao 'Set bid'"


def preencher_texto(campo, texto):
    """Escreve num campo de forma que o framework da Upwork registre.

    `fill` e' instantaneo e funciona no textarea da carta. `type` existe como reserva
    porque em alguns campos o `fill` nao dispara o handler deles.

    NAO use setter nativo de JS aqui: em varios `input` o campo fica visivelmente
    preenchido e o formulario continua dizendo que esta vazio, porque o Vue deles nunca
    soube da mudanca. Em `textarea` funciona; em `input` nao da' pra confiar."""
    campo.click()
    try:
        campo.fill("")
        campo.fill(texto)
        if (campo.input_value() or "").strip():
            return "fill"
    except Exception:
        pass
    campo.fill("")
    campo.type(texto, delay=4)
    return "type"


def main():
    acao = sys.argv[1] if len(sys.argv) > 1 else "estado"
    a1 = sys.argv[2] if len(sys.argv) > 2 else None
    a2 = sys.argv[3] if len(sys.argv) > 3 else None

    with sync_playwright() as p:
        try:
            br = p.chromium.connect_over_cdp(ALVO)
        except Exception as e:
            print("NAO CONECTEI em %s\n  %s" % (ALVO, str(e)[:200]))
            print("\nAbra o navegador A MAO com porta de depuracao antes de rodar isto.")
            raise SystemExit(1)

        pg = aba(br)

        if acao == "estado":
            u = pg.url
            print(json.dumps({
                "url": u[:140],
                "titulo": (pg.title() or "")[:90],
                "logado": ("login" not in u and "signup" not in u and "upwork.com" in u),
                "muro": bloqueado(pg),
                "abas": sum(len(c.pages) for c in br.contexts),
            }, ensure_ascii=False, indent=1))

        elif acao == "ir":
            pg.goto(a1, wait_until="domcontentloaded", timeout=90000)
            passou = esperar_passar(pg)
            print(json.dumps({"url": pg.url[:140], "titulo": (pg.title() or "")[:90],
                              "muro": not passou,
                              "esperou_desafio": True}, ensure_ascii=False, indent=1))

        elif acao == "ler":
            if a1:
                pg.goto(a1, wait_until="domcontentloaded", timeout=90000)
            if not esperar_passar(pg):
                print("MURO na tela. Resolva o checkbox e repita o comando."); raise SystemExit(2)
            for _ in range(3):
                pg.mouse.wheel(0, 2200); pg.wait_for_timeout(700)
            d = pg.evaluate(JS_LER)
            cam = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp", "upw2-ler.txt")
            os.makedirs(os.path.dirname(cam), exist_ok=True)
            io.open(cam, "w", encoding="utf-8").write(d["corpo"])
            print("titulo:", d["doc"][:90])
            print("h1    :", d["h1"])
            if d["skills"]:
                print("skills:", ", ".join(d["skills"])[:300])
            print("corpo salvo em:", cam, "(%d chars)" % len(d["corpo"]))


        elif acao == "campos":
            if not esperar_passar(pg):
                print("MURO na tela."); raise SystemExit(2)
            d = pg.evaluate(JS_CAMPOS)
            print("URL:", pg.url[:110])
            print("\n--- CAMPOS (%d) ---" % len(d["campos"]))
            for c in d["campos"]:
                print("  [%2d] %-9s %-26s max=%-5s %s| %s"
                      % (c["i"], c["tag"] + "/" + (c["tipo"] or "-"), c["rotulo"][:26],
                         c["max"] or "-", "MODAL " if c["dialogo"] else "      ",
                         (c["valor"] or "")[:40]))
            print("\n--- BOTOES ---")
            print("  " + " | ".join(("*" if b["dialogo"] else "") + b["t"] for b in d["botoes"]))

        elif acao == "set":
            if a1 is None or a2 is None:
                raise SystemExit('uso: set "<rotulo>" "<texto>"   (texto pode ser @arquivo.txt)')
            texto = a2
            if texto.startswith("@"):
                texto = io.open(texto[1:], encoding="utf-8").read().strip()
            c, d = achar_campo(pg, a1)
            if not c:
                print("Nao achei campo com rotulo contendo %r. Rode `campos` para ver a lista." % a1)
                raise SystemExit(3)
            if c["max"] and len(texto) > int(c["max"]):
                # limite silencioso ja custou uma candidatura inteira na Deel/AtomChat:
                # campo sem mensagem de erro, botao de enviar desabilitado pra sempre.
                print("RECUSADO: o campo %r aceita %s chars e o texto tem %d."
                      % (c["rotulo"], c["max"], len(texto)))
                raise SystemExit(4)
            # localiza pelo atributo que o proprio JS_CAMPOS carimbou. Antes era
            # nth(indice), mas o indice vinha da lista de VISIVEIS e o locator conta
            # todos, ocultos inclusive: nas telas com campo escondido eu escreveria no
            # campo errado sem erro nenhum.
            el = _loc(pg, c)
            el.scroll_into_view_if_needed()
            if c["tag"] == "select":
                el.select_option(label=texto)
            elif len(texto) > 300:
                # digitar 2.492 chars com delay por tecla estourou o teto de 30s.
                # fill() e' instantaneo e ainda dispara o evento input, que e' o que
                # framework controlado precisa ver.
                el.click(); el.fill(texto)
                el.press("End")
            else:
                el.click(); el.fill(""); el.type(texto, delay=5)
            pg.wait_for_timeout(700)
            conferido = (el.input_value() or "")
            if len(conferido) < min(len(texto), 40):
                print("ATENCAO: o campo ficou com %d chars, esperava %d." % (len(conferido), len(texto)))
            print("OK  %-28s <- %d chars" % (c["rotulo"][:28], len(texto)))


        elif acao == "skill":
            if not a1:
                raise SystemExit('uso: skill "<nome exato da skill>"')
            c, _ = achar_campo(pg, "search skills")
            if not c:
                print("Nao achei a busca de skills. O modal de skills esta aberto?")
                raise SystemExit(3)
            cx = _loc(pg, c)
            cx.click()
            cx.fill("")
            cx.type(a1, delay=45)
            pg.wait_for_timeout(2200)
            # a Upwork tem skill de nome parecido (ex "Google Analytics" x "Google
            # Analytics 4"). Exigir igualdade exata evita marcar a irma errada em silencio.
            op = pg.locator("[role='option'], li[role='option'], .air3-menu-item")
            n = op.count()
            escolhido = None
            for i in range(min(n, 14)):
                t = (op.nth(i).inner_text() or "").strip()
                if t.lower() == a1.lower():
                    escolhido = (i, t); break
            if escolhido is None:
                vistos = [(op.nth(i).inner_text() or "").strip()[:34] for i in range(min(n, 8))]
                print("SEM match exato para %r. Sugestoes: %s" % (a1, " | ".join(vistos)))
                raise SystemExit(4)
            op.nth(escolhido[0]).click()
            pg.wait_for_timeout(1200)
            print("+ %s" % escolhido[1])


        elif acao == "skills":
            if not a1:
                raise SystemExit('uso: skills "Skill A|Skill B|Skill C"')
            nomes = [n.strip() for n in a1.split("|") if n.strip()]
            c, _ = achar_campo(pg, "search skills")
            if not c:
                print("Modal de skills nao esta aberto."); raise SystemExit(3)
            add, faltou = [], []
            for nome in nomes:
                # tudo num processo so. Uma invocacao por skill fazia o React perder as
                # anteriores: das 8 adicionadas em 8 execucoes, so a ultima sobreviveu.
                cx = _loc(pg, c)
                cx.click()
                # NUNCA fill("") aqui. Em campo de tag, limpar input vazio equivale a
                # Backspace, e Backspace em input vazio REMOVE O ULTIMO CHIP. Foi assim
                # que cada skill nova comia a anterior, e o perfil caiu de 6 skills pra 3.
                cx.type(nome, delay=45)
                pg.wait_for_timeout(2200)
                # TECLADO, nao clique. Clicar a opcao mostrava sucesso mas a tag nao
                # commitava: das 12 adicionadas assim, so' a ultima sobrevivia ao Save.
                # Mesmo padrao que resolveu o vue-multiselect da Contractor Liberty.
                op = pg.locator("[role='option'], li[role='option'], .air3-menu-item")
                achou = None
                for i in range(min(op.count(), 14)):
                    t = (op.nth(i).inner_text() or "").strip()
                    if t.lower() == nome.lower():
                        achou = (i, t); break
                if achou is None:
                    faltou.append(nome); continue
                for _ in range(achou[0] + 1):
                    pg.keyboard.press("ArrowDown")
                    pg.wait_for_timeout(120)
                pg.keyboard.press("Enter")
                pg.wait_for_timeout(1200)
                add.append(achou[1])
            print("adicionadas (%d): %s" % (len(add), ", ".join(add)))
            if faltou:
                print("sem match exato: %s" % ", ".join(faltou))


        elif acao == "dialogo":
            # le SO' o modal aberto. `ler` traz o corpo inteiro e o texto da pagina de
            # fundo soterra a mensagem do modal, que e' justamente onde ficam limite de
            # itens e erro de validacao.
            d = pg.evaluate("""() => {
              const m = document.querySelector("[role='dialog'], .air3-modal, [class*='modal']");
              if (!m) return null;
              return (m.innerText || "").slice(0, 4000);
            }""")
            if not d:
                print("Nenhum modal aberto."); raise SystemExit(3)
            print(d)


        elif acao == "shot":
            cam = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp", "upw2-shot.png")
            os.makedirs(os.path.dirname(cam), exist_ok=True)
            pg.screenshot(path=cam, full_page=bool(a1))
            print(cam)


        elif acao == "js":
            if not a1:
                raise SystemExit('uso: js "<expressao javascript>"')
            r = pg.evaluate(a1 if a1.strip().startswith("(") or "=>" in a1 else "() => (%s)" % a1)
            print(json.dumps(r, ensure_ascii=False, indent=1)[:9000])


        elif acao == "dd":
            # dropdown proprio da Upwork (air3-dropdown): nao e select nativo, entao
            # select_option nao funciona. Abre o toggle pelo titulo e clica a opcao.
            if not (a1 and a2):
                raise SystemExit('uso: dd "<titulo do toggle>" "<valor>"')
            tog = pg.locator(".air3-dropdown-toggle-title", has_text=a1).first
            if not tog.count():
                print("Nao achei dropdown com titulo %r" % a1); raise SystemExit(3)
            tog.scroll_into_view_if_needed()
            tog.click()
            pg.wait_for_timeout(900)
            op = pg.locator("[role='option'], .air3-menu-item, li")
            alvo = None
            for i in range(min(op.count(), 200)):
                try:
                    t = (op.nth(i).inner_text() or "").strip()
                except Exception:
                    continue
                if t == a2:
                    alvo = i; break
            if alvo is None:
                print("Valor %r nao esta na lista do dropdown %r." % (a2, a1)); raise SystemExit(4)
            op.nth(alvo).click()
            pg.wait_for_timeout(900)
            print("dd %s = %s" % (a1, a2))

        elif acao == "clicar":
            if not a1:
                raise SystemExit('uso: clicar "<texto do botao>"')
            proibido = ("send", "submit proposal", "apply now and pay")
            if any(p in a1.lower() for p in proibido):
                print("RECUSADO: %r parece envio de proposta. Enviar e' clique seu, nunca meu." % a1)
                raise SystemExit(5)
            alvo = pg.get_by_role("button", name=a1, exact=False).first
            if not alvo.count():
                alvo = pg.locator("button:has-text(%r), a:has-text(%r)" % (a1, a1)).first
            if not alvo.count():
                print("Nao achei botao com texto %r." % a1); raise SystemExit(3)
            alvo.scroll_into_view_if_needed()
            alvo.click()
            pg.wait_for_timeout(2500)
            print("cliquei:", a1, "| url agora:", pg.url[:100])

        elif acao == "preparar":
            # Roda as correcoes conhecidas na tela de proposta e diz o que ainda falta.
            # Serve pra quando voce preencheu a mao e quer saber por que o Send nao vai.
            freq = resolver_reajuste(pg)
            print("reajuste de tarifa  ->", freq if freq else "nao existe (preco fixo)")
            if a1:
                print("lance de posicao    ->", confirmar_lance(pg, a1))
            pend = erros_do_form(pg)
            if pend:
                print()
                print("FALTA RESOLVER:")
                for x in pend:
                    print("  -", x)
            else:
                print()
                print("nenhum erro de validacao na tela.")
            print()
            print("NAO CLIQUEI EM SEND, e nao vou. Confira e envie voce.")

        elif acao == "propor":
            if not (a1 and a2):
                raise SystemExit("uso: propor <url-da-vaga> <arquivo-com-a-proposta>")
            texto = io.open(a2, encoding="utf-8").read().strip()
            pg.goto(a1, wait_until="domcontentloaded", timeout=90000)
            if not esperar_passar(pg):
                print("MURO nao caiu em 120s. Resolva o checkbox e repita."); raise SystemExit(2)

            # a maior textarea visivel e' a carta de apresentacao. Ancorar em classe da
            # Upwork quebra a cada deploy deles; tamanho nao quebra.
            melhor, area = 0, None
            for t in pg.locator("textarea").all():
                try:
                    if not t.is_visible():
                        continue
                    cx = t.bounding_box() or {}
                    tam = (cx.get("width", 0) or 0) * (cx.get("height", 0) or 0)
                    if tam > melhor:
                        melhor, area = tam, t
                except Exception:
                    continue
            if area is None:
                print("Nao achei a carta de apresentacao nesta tela.")
                print("Confira se voce ja clicou em Apply Now. URL atual:", pg.url[:120])
                raise SystemExit(3)

            preencher_texto(area, texto[:5000])
            pg.wait_for_timeout(600)

            # As tres armadilhas do formulario da Upwork, resolvidas antes de voce
            # descobrir do jeito caro (clicar em Send e nao acontecer nada).
            freq = resolver_reajuste(pg)
            if freq:
                print("reajuste de tarifa  ->", freq, "(e' obrigatorio, apesar de dizer optional)")

            pendentes = erros_do_form(pg)
            if pendentes:
                print("\nAINDA FALTA (o Send vai falhar sem isso):")
                for p in pendentes:
                    print("  -", p)

            escrito = (area.input_value() or "")
            print("PREENCHIDO: %d de %d chars." % (len(escrito), len(texto)))
            print("URL:", pg.url[:120])
            print("\nNAO CLIQUEI EM SEND, e nao vou. Confira na janela e envie voce.")

        else:
            raise SystemExit(__doc__)


main()
