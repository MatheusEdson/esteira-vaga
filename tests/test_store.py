# -*- coding: utf-8 -*-
"""Testes do armazenamento.

POR QUE AQUI E NÃO EM OUTRO LUGAR. `core/store.py` é onde um bug custa **dado**, não uma
nova tentativa: escrita atômica, lock de diretório, migração idempotente e a aritmética
cumulativa de `estatisticas()`. Um erro na classificação de e-mail você percebe lendo a
tela; um erro aqui apaga uma candidatura em silêncio.

Cada teste roda contra um diretório temporário, nunca contra o `data/` real.

Rodar:  python -m pytest tests/ -q
"""
import importlib
import json
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """store apontado para um diretório descartável."""
    import core.store as st
    importlib.reload(st)
    monkeypatch.setattr(st, "DIR", tmp_path, raising=False)
    for nome in ("VAGAS", "PERFIL", "LEDGER", "LOCK"):
        antigo = getattr(st, nome, None)
        if antigo is not None:
            monkeypatch.setattr(st, nome, tmp_path / os.path.basename(str(antigo)))
    return st


def test_adicionar_e_listar(store):
    store.adicionar("https://exemplo.com/vaga/1", "Empresa A", "Analista")
    vagas = store.listar()
    assert len(vagas) == 1
    assert vagas[0]["url"] == "https://exemplo.com/vaga/1"


def test_url_repetida_nao_duplica(store):
    """Candidatar-se duas vezes na mesma vaga e o erro que mais custa credibilidade.

    A segunda chamada devolve `duplicada: True` com a vaga que ja existia, em vez de
    levantar erro: quem cola a URL de novo quer ver o cartao, nao um traceback."""
    store.adicionar("https://exemplo.com/vaga/1", "Empresa A", "Analista")
    r = store.adicionar("https://exemplo.com/vaga/1", "Empresa A", "Analista")
    assert r["duplicada"] is True
    assert len(store.listar()) == 1


def test_escrita_e_atomica(store):
    """Não pode existir momento em que o arquivo esteja pela metade no disco.

    O arquivo final tem que ser JSON válido depois de cada escrita, e nenhum temporário
    pode sobrar: temporário órfão vira lixo que ninguém limpa e confunde na hora do
    diagnóstico.
    """
    for i in range(5):
        store.adicionar("https://exemplo.com/vaga/%d" % i, "E", "T")
        conteudo = json.loads(store.VAGAS.read_text(encoding="utf-8"))
        assert isinstance(conteudo, list)
    sobras = [p.name for p in store.VAGAS.parent.iterdir()
              if p.name.endswith(".tmp") or p.name.endswith("~")]
    assert not sobras, "sobrou temporario: %s" % sobras


def test_migrar_e_idempotente(store):
    """Rodar de novo não pode mudar nada.

    `migrar()` retorna quantos registros mudou. Se ela alterasse um campo sem contar,
    o resultado seria recalculado e descartado a cada chamada, para sempre.
    """
    store.adicionar("https://exemplo.com/vaga/1", "E", "T")
    vagas = store.listar()
    _, mudou_1 = store.migrar(vagas)
    _, mudou_2 = store.migrar(vagas)
    assert mudou_2 == 0, "migrar nao e idempotente: mudou %d na segunda passada" % mudou_2


def test_mover_registra_transicao(store):
    v = store.adicionar("https://exemplo.com/vaga/1", "E", "T")["vaga"]
    store.mover(v["id"], "enviada", "teste")
    assert store.listar()[0]["estado"] == "enviada"
    tr = store.transicoes(v["id"])
    assert tr and tr[-1]["para"] == "enviada"


def test_mover_para_estado_invalido_falha(store):
    """O vocabulário de estados é fechado de propósito: um estado inventado sai do Kanban
    e some da vista, sem erro nenhum."""
    v = store.adicionar("https://exemplo.com/vaga/1", "E", "T")
    with pytest.raises(Exception):
        store.mover(v["id"], "estado-que-nao-existe")


def test_estatisticas_conta_enviadas_de_forma_cumulativa(store):
    """Quem chegou em entrevista TAMBÉM foi enviada.

    Se `enviadas` contasse só o estado literal, a taxa de resposta passaria de 100%
    assim que alguém avançasse, e o número que orienta a decisão viraria ficção.
    """
    for i, estado in enumerate(["enviada", "respondida", "entrevista", "proposta"]):
        v = store.adicionar("https://exemplo.com/vaga/%d" % i, "E", "T")["vaga"]
        store.mover(v["id"], estado)

    e = store.estatisticas()
    assert e["enviadas"] == 4
    assert e["respostas"] == 3
    assert e["avancadas"] == 2
    assert e["taxa_resposta"] == 75.0
    assert e["total"] == 4


def test_estatisticas_sem_vagas_nao_divide_por_zero(store):
    e = store.estatisticas()
    assert e["taxa_resposta"] == 0.0
    assert e["taxa_avanco"] == 0.0
    assert e["total"] == 0
