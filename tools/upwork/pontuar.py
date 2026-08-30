"""Pontua o lote que veio do Apify e diz onde vale gastar Connect.

  python pontuar.py <arquivo-do-dataset.json>

Existe porque o recurso escasso nao e' vaga, e' CONNECT. Medido na conta em 26/08: a vaga
boa custa 17 Connects, algumas custam 0, e o saldo era 170 com reposicao de 100/mes no
Plus. Ou seja, cerca de 10 propostas nas caras. Errar tres queima meio mes.

O corte NAO e' por afinidade de palavra-chave. Vaga com titulo perfeito e cliente que nunca
gastou um dolar e' pior que vaga morna com cliente de 245 mil. A ordem dos fatores aqui e:
o cliente paga? o cliente contrata? quantos ja chegaram na frente? e so' entao, cabe?

E le' o TEXTO da vaga, nao so' os metadados. A versao anterior aprovou uma vaga que exigia
"5+ years" e proibia quem tem emprego integral, ambos veto explicito no NUNCA_AFIRMAR, e
teria custado 17 Connects para ser reprovado ja na leitura do cliente.
"""
import sys, io, json, re

# Do perfil.json. Declarar isso como skill puxa convite que ele nao entrega.
# TikTok e LinkedIn sairam do veto em 29/08/2026: ele JA rodou campanha nos dois
# (e Taboola), em nivel basico. Nao e a especialidade, mas opera. Vetar cortava
# vaga boa de 3 canais onde ele cobre 2 com profundidade.
VETO_SKILL = ("link building",)
PISO_HORA = 15          # abaixo disso nao paga o tempo dele nem como historico
PISO_FIXO = 100

# Vetos que so' aparecem no corpo do anuncio.
VETO_TEXTO = [
    # So' casa EXIGENCIA DE MINIMO de 4 anos pra cima. Um range tipo "3-5 years" pede
    # minimo 3 e ele qualifica; vetar isso perderia vaga boa. Por isso o numero tem que
    # vir colado num marcador de minimo: o "+" ou "at least" / "minimum of" / "over".
    # Precisa de contexto de EXIGENCIA. Sem ele, o regex pegava o cliente se descrevendo
    # ("our agency has 5+ years of experience", "we are a team with over 10 years") e
    # vetava vaga boa, num arquivo cuja premissa e nao desperdicar Connect. A vaga
    # descartada nunca aparece, entao o erro era invisivel.
    (r"do not apply if you have a full[- ]time", "proibe quem tem emprego integral"),
    (r"no full[- ]time (?:job|position|role) elsewhere", "proibe quem tem emprego integral"),
    (r"must be (?:a )?(?:us|u\.s\.|united states|usa)[- ]based", "exige residir nos EUA"),
    # (r"tiktok ads?", "exige TikTok Ads (proibido)"),  # removido: ele opera no basico
    # (r"linkedin ads?", "exige LinkedIn Ads (proibido)"),  # removido: ele opera no basico
    (r"link building", "exige link building (proibido)"),
    # Ele TEM as certificacoes Google Ads (Search, AI-Powered Performance, Measurement,
    # vigentes ate 21/06/2027). Este veto derrubou a vaga LSA+GHL por engano em 26/08.
    # So' Meta Blueprint continua sendo veto.
    (r"meta blueprint", "exige Meta Blueprint, que ele nao tem"),
]



# Anos de experiencia: quatro casos que um regex so' nao separa.
#
#   "our agency has 5+ years"          o CLIENTE se descrevendo   -> passa
#   "we are a team with over 10 years" idem                       -> passa
#   "you must have 5+ years"           exigencia real             -> veta
#   "looking for 3-5 years"            faixa com minimo 3         -> passa, ele cabe
#
# A versao anterior era um regex sem ancora de contexto e pegava os dois primeiros. Num
# arquivo cuja premissa e nao desperdicar Connect, o custo do falso veto e invisivel: a
# vaga descartada nunca aparece na tela para alguem desconfiar.
PEDE = (r"(?:you (?:must|should|will need to) have|must have|should have|require[sd]?|"
        r"requirement|qualification|looking for|seeking|we need|candidate (?:must|should)|"
        r"minimum(?: of)?|at least)")
FALA_DE_SI = r"(?:we|our|us|the (?:agency|company|team)|i)\b"


def _exige_anos(texto, minimo_dele=3):
    """Devolve motivo se a vaga EXIGE mais anos do que ele tem. Senao, None."""
    for m in re.finditer(r"(\d{1,2})\s*(?:-|to|a)\s*(\d{1,2})\s*\+?\s*years?", texto):
        # Faixa: o que vale e o piso. "3-5 years" pede 3, e ele cabe.
        if int(m.group(1)) <= minimo_dele:
            texto = texto[:m.start()] + " " + texto[m.end():]

    for m in re.finditer(r"(\d{1,2})\s*\+?\s*years?", texto):
        n = int(m.group(1))
        if n <= minimo_dele:
            continue
        antes = texto[max(0, m.start() - 90):m.start()]
        # Se o sujeito mais proximo antes do numero e o proprio cliente, e apresentacao,
        # nao exigencia.
        pede = re.search(PEDE + r"[^.]{0,60}$", antes)
        si = re.search(FALA_DE_SI + r"[^.]{0,60}$", antes)
        if si and (not pede or si.start() > pede.start()):
            continue
        if pede or re.search(r"\+\s*years?", m.group(0)):
            return "exige %d+ anos; ele tem ~%d" % (n, minimo_dele)
    return None


def dinheiro(s):
    if s is None:
        return None
    n = re.findall(r"[\d.]+", str(s).replace(",", ""))
    return float(n[0]) if n else None


def vetos_do_texto(v):
    alvo = ((v.get("description") or "") + " " + (v.get("title") or "")).lower()
    achados = [motivo for padrao, motivo in VETO_TEXTO if re.search(padrao, alvo)]
    anos = _exige_anos(alvo)
    if anos:
        achados.append(anos)
    return achados


def avaliar(v):
    prop = v.get("proposals")
    gasto = v.get("clientTotalSpent") or 0
    taxa = v.get("clientHireRatePercent") or 0
    nota = v.get("clientRating") or 0
    verif = bool(v.get("paymentVerified"))
    tipo = (v.get("jobType") or "").lower()
    orc = dinheiro(v.get("budget"))
    tags = " ".join(v.get("tags") or []).lower()
    titulo = (v.get("title") or "").lower()

    pago_hora = v.get("clientAvgHourlyRate")

    cortes = []
    if not verif:
        cortes.append("pagamento NAO verificado")
    if gasto == 0 and (prop or 0) > 25:
        cortes.append("cliente nunca gastou e ja tem %s propostas" % prop)

    # O MELHOR previsor de vaga ruim nao e' o orcamento anunciado, e' o que o cliente ja
    # pagou de fato. Caso real: descricao impecavel pedindo especialista em CAPI, com
    # workflows de IA e GEO, escrita como se fosse feita sob medida. O cliente tinha 625
    # vagas publicadas, US$15 mil gastos e media de US$5,74/hora. A descricao seduz; o
    # historico nao mente. Sem esta regra, custaria 17 Connects para descobrir.
    if pago_hora is not None and PISO_HORA and pago_hora < PISO_HORA * 0.6:
        cortes.append("cliente paga $%.2f/h de media, muito abaixo do seu piso de $%g"
                      % (pago_hora, PISO_HORA))
    if tipo == "hourly" and orc is not None and orc < PISO_HORA:
        cortes.append("teto horario $%g abaixo do piso" % orc)
    if tipo == "fixed" and orc is not None and orc < PISO_FIXO:
        cortes.append("fixo $%g abaixo do piso" % orc)
    for veto in VETO_SKILL:
        if veto in tags or veto in titulo:
            cortes.append("exige %s (proibido)" % veto)
    cortes.extend(vetos_do_texto(v))

    # Pontos. Cliente que paga e contrata pesa mais que fila curta.
    p = 0
    p += min(gasto / 10000.0, 6) * 5          # ate 30 por historico de gasto
    p += (taxa / 100.0) * 25                  # ate 25 por taxa de contratacao
    p += min(nota, 5) * 3                     # ate 15 por reputacao
    if prop is not None and prop < 25:        # ate 25 por fila curta
        p += 25 - prop
    if verif:
        p += 5
    return round(p, 1), cortes


def main():
    caminho = sys.argv[1] if len(sys.argv) > 1 else None
    if not caminho:
        raise SystemExit(__doc__)

    d = json.load(io.open(caminho, encoding="utf-8"))
    itens = d.get("items", d) if isinstance(d, dict) else d

    bons, ruins = [], []
    for v in itens:
        p, cortes = avaliar(v)
        (ruins if cortes else bons).append((p, cortes, v))
    bons.sort(key=lambda x: -x[0])
    ruins.sort(key=lambda x: -x[0])

    print("=" * 78)
    print("VALE CONNECT  (%d)" % len(bons))
    print("=" * 78)
    for p, _, v in bons:
        print("\n[%5.1f] %s" % (p, (v.get("title") or "")[:70]))
        print("        %s | %s | propostas: %s"
              % (v.get("budget"), v.get("jobType"), v.get("proposals")))
        print("        cliente: $%s gasto, %s%% contrata, nota %s, %s"
              % (v.get("clientTotalSpent"), v.get("clientHireRatePercent"),
                 v.get("clientRating"), v.get("clientLocation")))
        print("        %s" % (v.get("url") or "")[:110])

    print("\n" + "=" * 78)
    print("NAO GASTAR  (%d)" % len(ruins))
    print("=" * 78)
    for p, cortes, v in ruins:
        print("[%5.1f] %-52s  <- %s"
              % (p, (v.get("title") or "")[:52], "; ".join(cortes)))


if __name__ == "__main__":
    main()
