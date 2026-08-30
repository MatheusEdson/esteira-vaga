# -*- coding: utf-8 -*-
"""Tudo que todo adaptador precisa, num import só.

POR QUE EXISTE. Os 16 adaptadores repetiam o mesmo cabeçalho de ~18 linhas: manipulação de
`sys.path`, carga do perfil, `ID = PERFIL["identidade"]`, um `do_perfil()` idêntico em 7
arquivos, e a resolução de currículo e anexo. Deu 26% de duplicação medida, e o custo real
não é estética: quando o caminho do perfil estava errado, o mesmo bug precisou ser
corrigido em 17 arquivos. Um lugar errado é um bug; dezessete lugares errados é uma
política errada.

COMO USAR, no topo do adaptador:

    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core.bootstrap import PERFIL, ID, do_perfil, cv, anexo, resposta, sync_playwright

As duas primeiras linhas continuam necessárias porque o repositório não é um pacote
instalável: os adaptadores rodam como `python adapters/aplicar_x.py`, e sem elas o Python
não acha `core/`. Empacotar resolveria, ao custo de reestruturar 20 arquivos para um ganho
que nenhum usuário sente.
"""
from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

import sys
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Reexportado daqui, e não importado direto do patchright, porque o nav.py aplica
# chromium_sandbox=True por padrão. Ver nav.py.
from nav import sync_playwright, ErroTempo  # noqa: E402,F401

from core.perfil import (  # noqa: E402
    perfil as _perfil,
    curriculo as cv,
    anexo,
    respostas_md,
)

PERFIL = _perfil()
ID = PERFIL["identidade"]
RESP = PERFIL.get("respostas_padrao", {})
AN = PERFIL.get("anexos", {})

__all__ = ["PERFIL", "ID", "RESP", "AN", "RAIZ", "do_perfil", "cv", "anexo",
           "resposta", "bloco", "tmp", "sync_playwright", "ErroTempo"]


def do_perfil(chave: str, secao: str = "respostas_padrao") -> str:
    """Lê do perfil e ABORTA se estiver vazio.

    Vazio aborta de propósito. Um formulário respondido com valor inventado é pior que um
    formulário não enviado: o erro chega ao outro lado como afirmação sua.
    """
    v = PERFIL.get(secao, {}).get(chave)
    v = str(v).strip() if v is not None else ""
    if not v:
        raise SystemExit(
            "ERRO: preencha %s.%s no data/perfil.json\n"
            "O adaptador para em vez de inventar resposta. É de propósito." % (secao, chave))
    return v


def resposta(nome_arquivo: str) -> str:
    """Caminho de um arquivo de respostas, validando existência."""
    caminho = respostas_md(nome_arquivo)
    if not os.path.exists(caminho):
        raise SystemExit(
            "ERRO: não achei %s\n"
            "Formato em docs/respostas-formato.md." % caminho)
    return caminho


def bloco(chave: str, nome_arquivo: str = "") -> str:
    """Uma seção `## CHAVE` de um arquivo em respostas/.

    As respostas dissertativas ficam fora do código porque carregam número de empregador e
    de cliente. respostas/ é gitignored. Ver docs/respostas-formato.md.
    """
    import inspect
    import io
    import re
    if not nome_arquivo:
        # Deduz pelo modulo que chamou: aplicar_deel_atomchat.py -> deel_atomchat.md.
        # Assim o adaptador escreve `bloco("ANOS_GTM")` e nao repete o nome do arquivo em
        # cada chamada, que era como funcionava antes de virar helper compartilhado.
        quadro = inspect.stack()[1]
        base = os.path.basename(quadro.filename)
        nome_arquivo = (base.replace("aplicar_", "").replace("preencher_", "")
                        .replace(".py", ".md"))
    caminho = resposta(nome_arquivo)
    txt = io.open(caminho, encoding="utf-8").read()
    m = re.search(r"^##\s+" + re.escape(chave) + r"\s*$(.*?)(?=^##\s|\Z)", txt, re.M | re.S)
    if not m or not m.group(1).strip():
        raise SystemExit("ERRO: falta a seção '## %s' em %s" % (chave, caminho))
    return m.group(1).strip()


def tmp(nome: str) -> str:
    """Caminho para artefato descartável, sempre em _tmp/ na raiz.

    Antes cada adaptador escrevia em `_tmp/` ao lado de si mesmo, então os screenshots
    ficavam espalhados por `adapters/_tmp/`, `core/_tmp/` e `tools/upwork/_tmp/`, e só um
    desses estava no .gitignore.
    """
    d = RAIZ / "_tmp"
    d.mkdir(exist_ok=True)
    return str(d / nome)
