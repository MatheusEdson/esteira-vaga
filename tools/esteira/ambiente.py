# -*- coding: utf-8 -*-
"""Carrega o .env para o ambiente do processo.

POR QUE EXISTE. A documentacao manda criar um `.env` com cinco variaveis e depois rodar
`python tools/esteira/esteira.py`. So' que nenhum modulo carregava esse arquivo: o `db.py`
fazia parse manual e SO' da propria chave dele. Resultado, o `.env` funcionava por cron
(porque `scripts/cron-esteira.sh` faz `set -a && . ./.env`) e era inerte a mao.

O modo de falhar era silencioso, que e' o pior tipo: sem `MEUS_EMAILS`, o `gmail_vagas.py`
ficava com `EU = []`, `eu_mandei` nunca era detectado, e a "prova de que VOCE respondeu"
simplesmente sumia do quadro. Nenhum erro, nenhum aviso.

Nao usa python-dotenv de proposito: sao 20 linhas e uma dependencia a menos para instalar.

ANCORA NA RAIZ DO REPO, nao no diretorio atual. `os.environ.get("ENV_FILE", ".env")` era
relativo ao cwd, entao rodar de outro diretorio lia o `.env` que estivesse la, que num
diretorio gravavel por outra pessoa e' leitura de credencial alheia.
"""
import io
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent


def caminho():
    indicado = os.environ.get("ENV_FILE")
    if indicado:
        p = Path(indicado)
        return p if p.is_absolute() else RAIZ / p
    return RAIZ / ".env"


def carregar(sobrescrever=False):
    """Le o .env para os.environ. Variavel ja' definida no ambiente vence, por padrao:
    quem exportou a mao ou pelo cron tinha uma intencao mais especifica que o arquivo."""
    p = caminho()
    if not p.exists():
        return 0
    n = 0
    for linha in io.open(p, encoding="utf-8", errors="replace"):
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        if not chave or (not sobrescrever and chave in os.environ):
            continue
        os.environ[chave] = valor
        n += 1
    return n
