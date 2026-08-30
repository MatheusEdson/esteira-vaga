"""Perfil e os formatos derivados dele.

Por que este modulo existe: o MESMO dado precisa de formato diferente por ATS, e isso
nao e' capricho. Um formulario recusou "Curitiba, PR, Brasil" com "Please enter a
valid answer" e aceitou "Curitiba, Brazil". Outro quer telefone so' com digitos, outro
quer E.164, outro quer com codigo de pais mas sem o sinal de mais.

Antes disso, cada adaptador tinha o valor cravado no codigo. Duas consequencias ruins:
mudar de telefone exigia editar 12 arquivos, e o repo nao servia para outra pessoa.
Agora tudo sai de data/perfil.json e nenhum dado pessoal vive em codigo versionado.
"""
from __future__ import annotations
import json, unicodedata
from functools import lru_cache
from pathlib import Path

PERFIL_JSON = Path(__file__).resolve().parent.parent / "data" / "perfil.json"

_UF = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia",
    "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás",
    "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia",
    "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}
_PAIS_EN = {"brasil": "Brazil", "brazil": "Brazil"}


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=1)
def _bruto() -> dict:
    if not PERFIL_JSON.exists():
        raise SystemExit(
            "ERRO: nao achei %s\n"
            "Copie perfil.example.json para data/perfil.json e preencha." % PERFIL_JSON)
    return json.loads(PERFIL_JSON.read_text(encoding="utf-8"))


def perfil() -> dict:
    return _bruto()


def ident(chave: str, default: str = "") -> str:
    v = _bruto().get("identidade", {}).get(chave, default)
    return v if isinstance(v, str) else (default if v is None else str(v))


def resposta(chave: str, default: str = "") -> str:
    v = _bruto().get("respostas_padrao", {}).get(chave, default)
    return v if isinstance(v, str) else (default if v is None else str(v))


def curriculo(trilha: str) -> str:
    """Caminho do CV para a trilha. Resolve relativo a' raiz do repo."""
    nome = _bruto().get("curriculos", {}).get(trilha, "")
    if not nome:
        raise KeyError("trilha de curriculo desconhecida: %s. Disponiveis: %s"
                       % (trilha, ", ".join(_bruto().get("curriculos", {}))))
    p = Path(nome)
    return str(p if p.is_absolute() else PERFIL_JSON.parent.parent / "curriculos" / nome)


def anexo(chave: str) -> str:
    """Anexo por chave. URL volta como URL; nome de arquivo vira caminho absoluto.

    O bloco `anexos` mistura os dois de proposito: `vocaroo_30s` e `loom_intro` sao
    link, `speedtest` e `portfolio_pdf` sao arquivo que o adaptador precisa subir.
    Arquivo procura em anexos/ e, se nao achar, em curriculos/ (onde vivem os PDF).
    """
    v = str(_bruto().get("anexos", {}).get(chave, "") or "")
    if not v or v.startswith(("http://", "https://")):
        return v
    p = Path(v)
    if p.is_absolute():
        return str(p)
    raiz = PERFIL_JSON.parent.parent
    for pasta in ("anexos", "curriculos"):
        cand = raiz / pasta / v
        if cand.exists():
            return str(cand)
    return str(raiz / "anexos" / v)


def respostas_md(nome_arquivo: str) -> str:
    """Caminho de um arquivo de respostas dissertativas em respostas/."""
    p = Path(nome_arquivo)
    if p.is_absolute():
        return str(p)
    return str(PERFIL_JSON.parent.parent / "respostas" / nome_arquivo)


# ------------------------------------------------------------------ nome
def nome() -> str:
    return ident("nome_completo")


def primeiro() -> str:
    return ident("first_name")


def sobrenome() -> str:
    return ident("last_name")


def nome_dois_primeiros() -> str:
    """Alguns ATS separam em First/Last e esperam o nome do meio junto do primeiro."""
    partes = nome().split()
    return " ".join(partes[:2]) if len(partes) > 1 else primeiro()


def email() -> str:
    return ident("email")


def linkedin() -> str:
    return ident("linkedin_url")


def portfolio() -> str:
    """URL unica de portfolio. Se o perfil trouxer lista, usa a primeira."""
    v = _bruto().get("identidade", {}).get("portfolio", "")
    if isinstance(v, list):
        return v[0] if v else ""
    return str(v or "")


# ------------------------------------------------------------------ telefone
def _digitos(s: str) -> str:
    return "".join(c for c in (s or "") if c.isdigit())


def tel_e164() -> str:
    """Ex: +5541988887777 (E.164)"""
    e = ident("telefone_e164")
    return e if e.startswith("+") else "+" + _digitos(e)


def tel_formatado() -> str:
    """Ex: +55 41 98888-7777 (como o humano escreve)"""
    return ident("telefone_formatado") or tel_e164()


def tel_com_pais() -> str:
    """Ex: 5541988887777. Digitos, com pais, sem o sinal de mais."""
    return _digitos(tel_e164())


def tel_nacional() -> str:
    """Ex: 41988887777. DDD e numero, sem o codigo do pais."""
    d = tel_com_pais()
    ddi = _digitos(ident("ddi", "55")) or "55"
    return d[len(ddi):] if d.startswith(ddi) else d


def ddi() -> str:
    d = tel_com_pais()
    return d[:2] if len(d) > 10 else "55"


# ------------------------------------------------------------------ local
def cidade() -> str:
    return ident("cidade")


def uf() -> str:
    return ident("estado")


def estado_nome() -> str:
    return _UF.get(uf().upper(), uf())


def pais() -> str:
    return ident("pais")


def pais_en() -> str:
    return _PAIS_EN.get(pais().strip().lower(), pais())


def fuso() -> str:
    """Codigo curto do fuso, ex: UTC-3.

    GOTCHA: nao use respostas_padrao.fuso_disponivel aqui. Aquele campo e' prosa para
    responder "que fusos voce cobre" e devolve frase, nao codigo. Colocar frase dentro
    de "Cidade, Pais (fuso)" gera bobagem no formulario.
    """
    return ident("fuso") or "UTC-3"


def cidade_uf() -> str:
    """Ex: Curitiba, PR"""
    return "%s, %s" % (cidade(), uf())


def cidade_uf_pais() -> str:
    """Ex: Curitiba, PR, Brasil"""
    return "%s, %s, %s" % (cidade(), uf(), pais())


def cidade_estado_pais_en() -> str:
    """Ex: Curitiba, Parana, Brazil"""
    return "%s, %s, %s" % (cidade(), estado_nome(), pais_en())


def cidade_pais_en() -> str:
    """Ex: Curitiba, Brazil. Sem acento e sem UF.

    GOTCHA: e' esta a forma que passa em formulario chato. Ja vi campo recusar
    "Curitiba, PR, Brasil" com "Please enter a valid answer" e aceitar esta.
    """
    return "%s, %s" % (sem_acento(cidade()), pais_en())


def cidade_pais_fuso() -> str:
    """Ex: Curitiba, Brazil (UTC-3)"""
    return "%s (%s)" % (cidade_pais_en(), fuso())


def cidade_estado_en() -> str:
    """Ex: Curitiba, Parana"""
    return "%s, %s" % (cidade(), estado_nome())
