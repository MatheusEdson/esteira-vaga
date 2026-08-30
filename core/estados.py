"""Estados da candidatura: o vocabulario fechado que o Kanban precisa.

O problema que isto resolve: no JSON original o campo `status` era texto livre, e 34
registros produziram 12 estados diferentes, com "ENVIADA e confirmada (URL virou
/confirmation)" e "ENVIADA e CONFIRMADA" convivendo. Kanban precisa de coluna.

A solucao NAO e' jogar o texto fora. Ele e' a prova de envio e as vezes a unica coisa
que distingue "achei que enviei" de "enviei". Entao o registro passa a ter dois campos:

  estado          -> enum fechado, define a coluna do Kanban
  status_detalhe  -> o texto original, preservado inteiro

`classificar()` deriva o estado a partir do texto legado. A ordem das regras importa:
a primeira que casar ganha, e as regras mais especificas vem antes.
"""
from __future__ import annotations
import re

# ordem = ordem das colunas no Kanban, da esquerda para a direita
COLUNAS = [
    ("descoberta", "Descoberta",  "achada, ainda nao avaliada"),
    ("fila",       "Na fila",     "travada por pergunta sem resposta, login ou captcha"),
    ("enviada",    "Enviada",     "submissao confirmada"),
    ("respondida", "Respondeu",   "houve retorno humano do recrutador"),
    ("entrevista", "Entrevista",  "conversa marcada ou realizada"),
    ("proposta",   "Proposta",    "oferta recebida, com numero na mesa"),
    ("rejeitada",  "Rejeitada",   "recusa explicita"),
    ("nao_enviar", "Nao enviar",  "vetada de proposito: duplicata, fraude, ou fora de escopo"),
]
ESTADOS = [c[0] for c in COLUNAS]

# estado -> True se ainda conta como "vivo" no funil
VIVO = {"descoberta": True, "fila": True, "enviada": True, "respondida": True,
        "entrevista": True, "proposta": True, "rejeitada": False, "nao_enviar": False}

# A ordem aqui e' a ordem de avaliacao. Especifico antes de generico.
_REGRAS = [
    ("nao_enviar", r"\bNAO ENVIAR\b|\bNÃO ENVIAR\b|duplicata|fraude|descartada"),
    ("rejeitada",  r"\bREJEITADA\b|\brecusad|\bnot moving forward|another candidate"),
    # proposta antes de entrevista e de enviada: oferta e' o estado mais avancado, e o
    # texto quase sempre carrega tambem "entrevista" e "enviada" da historia anterior.
    ("proposta",   r"\bPROPOSTA\b|\boferta\b|\boffer\b|\bproposal\b|"
                   r"carta oferta|offer letter|job offer"),
    # "AVANCOU" vem antes de entrevista E de enviada: a string costuma conter as tres.
    # Sem isso, uma vaga que so' avancou e menciona "proximo passo: entrevista" e'
    # classificada como entrevista, que e' adiantar etapa que nao aconteceu.
    ("respondida", r"\bAVANCOU\b|\bAVANÇOU\b|respondeu|moveu para a proxima|next step"),
    # entrevista exige PROVA de que ocorreu ou esta marcada, nao mera mencao.
    ("entrevista", r"entrevista (j[aá] )?(feita|realizada|marcada|agendada)|"
                   r"interview (done|completed|scheduled|booked)|"
                   r"\bENTREVISTA J[AÁ] FEITA\b"),
    ("fila",       r"\bNAO ENVIADA\b|\bNÃO ENVIADA\b|\bFILA\b|\bBLOQUEADA\b|"
                   r"AGUARDANDO O CLIQUE|PREENCHIDA E AGUARDANDO|abandonada|ABANDONADA"),
    ("enviada",    r"\bENVIADA\b|\bENVIADO\b|submitted|application (was )?(sent|received)"),
]


def classificar(status_texto: str | None) -> str:
    """Deriva o estado fechado a partir do status legado em texto livre."""
    t = (status_texto or "").strip()
    if not t:
        return "descoberta"
    for estado, padrao in _REGRAS:
        if re.search(padrao, t, re.I):
            return estado
    return "descoberta"


def rotulo(estado: str) -> str:
    for e, r, _ in COLUNAS:
        if e == estado:
            return r
    return estado


def valido(estado: str) -> bool:
    return estado in ESTADOS
