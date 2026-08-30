# -*- coding: utf-8 -*-
"""Testes do veto por anos de experiencia.

Existem porque o custo do erro aqui e' INVISIVEL. Um falso veto descarta a vaga antes de
ela aparecer na tela, entao ninguem desconfia: voce so' vê menos oportunidade e conclui
que o mercado esta fraco. Num arquivo cuja premissa e' nao desperdiciar Connect, o falso
negativo custa mais que o falso positivo.

O regex anterior nao tinha ancora de contexto e vetava o CLIENTE se descrevendo
("our agency has 5+ years"), que e' texto de venda, nao requisito.

Rodar:  python -m pytest tests/ -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "upwork"))

import pontuar as P


def vetou(descricao):
    return bool(P.vetos_do_texto({"description": descricao, "title": ""}))


# ------------------------------------------------- cliente falando de si ----

def test_cliente_se_descrevendo_nao_e_exigencia():
    assert not vetou("Our agency has 5+ years of experience in paid media.")
    assert not vetou("We are a team with over 10 years serving ecommerce brands.")
    assert not vetou("We have been running ads for 8 years. You need 2+ years.")


# -------------------------------------------------------- exigencia real ----

def test_exigencia_acima_do_que_ele_tem_veta():
    assert vetou("You must have 5+ years of experience with Google Ads.")
    assert vetou("Requirements: at least 6 years in performance marketing.")


def test_exigencia_que_ele_atende_passa():
    assert not vetou("You must have 3+ years of experience.")


# ---------------------------------------------------------------- faixas ----

def test_faixa_vale_pelo_piso():
    """"3-5 years" pede minimo 3, e ele cabe. Vetar isso perdia vaga boa."""
    assert not vetou("Looking for someone with 3-5 years of experience.")
    assert vetou("Looking for someone with 6-8 years of experience.")


def test_sem_mencao_a_anos_passa():
    assert not vetou("Need a media buyer for Meta and Google campaigns.")


# ------------------------------------------------------------- orcamento ----

def test_veto_por_media_paga_pelo_cliente():
    """O melhor previsor de vaga ruim nao e' o orcamento anunciado, e' o que o cliente ja'
    pagou. Caso real: descricao impecavel, 625 vagas publicadas, media de US$5,74/hora."""
    _, cortes = P.avaliar({
        "title": "Meta Ads Specialist", "jobType": "hourly", "budget": "$50",
        "paymentVerified": True, "clientAvgHourlyRate": 5.74, "proposals": 5,
        "clientTotalSpent": 15000, "description": "",
    })
    assert any("muito abaixo do seu piso" in c for c in cortes)
