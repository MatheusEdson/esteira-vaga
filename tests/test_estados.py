# -*- coding: utf-8 -*-
"""Testes da derivação de estado do cartão.

ATENÇÃO ao que este módulo NÃO é. `core/estados.classificar()` lê o campo `status` de um
cartão do Kanban, que é texto livre herdado, e devolve um estado do vocabulário fechado.
Ele não classifica e-mail: isso é `tools/esteira/gmail_vagas.py`, com outro vocabulário e
outra entrada. Confundir os dois leva a "os classificadores discordam", que não é o caso.

O que vale testar aqui é a ORDEM das regras, que é onde mora o raciocínio: um status real
quase sempre carrega o histórico inteiro ("enviada, avançou, próximo passo entrevista"), e
o primeiro padrão que casar decide.

Rodar:  python -m pytest tests/ -q
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from core.estados import classificar, valido, ESTADOS  # noqa: E402


def test_vazio_vira_descoberta():
    assert classificar(None) == "descoberta"
    assert classificar("") == "descoberta"
    assert classificar("   ") == "descoberta"


def test_proposta_ganha_do_historico_anterior():
    """Oferta é o estado mais avançado, e o texto carrega a história toda."""
    assert classificar("ENVIADA, entrevista feita, PROPOSTA recebida") == "proposta"


def test_avancou_nao_vira_entrevista():
    """"Próximo passo: entrevista" é uma etapa que ainda NÃO aconteceu.

    Classificar como entrevista adianta o funil e faz a taxa de avanço mentir para cima.
    """
    assert classificar("AVANCOU. proximo passo: entrevista") == "respondida"


def test_entrevista_exige_prova_de_que_ocorreu():
    assert classificar("entrevista marcada para sexta") == "entrevista"
    assert classificar("entrevista ja feita") == "entrevista"
    # menção solta não basta
    assert classificar("ENVIADA. processo tem entrevista tecnica") == "enviada"


def test_rejeitada_ganha_de_enviada():
    assert classificar("ENVIADA. REJEITADA por outro candidato") == "rejeitada"


def test_fila_nao_e_enviada():
    """O oposto do erro caro: marcar como enviada algo que travou é perder a vaga em
    silêncio, porque ela sai da lista de coisas a fazer."""
    assert classificar("NAO ENVIADA - FILA, aguardando o clique") == "fila"


def test_nao_enviar_tem_prioridade_maxima():
    assert classificar("NAO ENVIAR - duplicata") == "nao_enviar"


def test_todo_estado_produzido_e_valido():
    """O vocabulário é fechado. Um estado fora dele some do Kanban sem erro nenhum."""
    amostras = ["", "ENVIADA", "REJEITADA", "PROPOSTA", "AVANCOU", "FILA",
                "NAO ENVIAR", "entrevista marcada", "texto que nao casa com nada"]
    for s in amostras:
        e = classificar(s)
        assert valido(e), "%r produziu estado invalido: %r" % (s, e)
        assert e in ESTADOS
