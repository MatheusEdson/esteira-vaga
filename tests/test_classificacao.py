# -*- coding: utf-8 -*-
"""Testes das regras de classificacao de e-mail.

Por que estes testes existem: cada caso aqui e' uma mensagem REAL que a esteira classificou
errado em producao. O teste nao esta provando que o codigo funciona; esta impedindo que
volte a falhar do jeito que ja falhou.

Rodar:  python -m pytest tests/ -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "esteira"))

import gmail_vagas as G


# --------------------------------------------------------------- acentos ----

def test_sem_acento_normaliza():
    assert G.sem_acento("está contratando") == "esta contratando"
    assert G.sem_acento("INSCRIÇÕES") == "inscricoes"
    assert G.sem_acento("") == ""


def test_ruido_de_assunto_pega_com_e_sem_acento():
    """O bug: a lista dizia 'esta contratando' e o assunto real vinha 'está contratando'.
    Doze alertas do LinkedIn vazaram por causa de um acento."""
    com = G.sem_acento("A empresa Neon está contratando para um cargo de Fintech")
    sem = G.sem_acento("A empresa Neon esta contratando para um cargo de Fintech")
    assert any(p in com for p in G.RUIDO_ASSUNTO)
    assert any(p in sem for p in G.RUIDO_ASSUNTO)


# ------------------------------------------------------------ rejeicoes ----

def test_rejeicao_em_portugues():
    """O bug: a regra so' conhecia 'unfortunately'. Uma rejeicao real passou batido por
    dizer 'optamos por seguir com outros perfis'."""
    estado, _ = G.classificar(
        "Retorno do Processo Seletivo\n"
        "Apos a conclusao das etapas, optamos por seguir com outros perfis que, "
        "neste momento, estao mais alinhados com alguns criterios da posicao.")
    assert estado == "rejeitada"


def test_rejeicao_em_portugues_que_menciona_entrevista():
    """O bug: a regra `entrevista` vinha ANTES de `rejeitada` e casava a palavra nua, entao
    "agradecemos sua participacao na entrevista, optamos por outros perfis" era classificado
    como entrevista. Assimetrico: em ingles acertava, porque "unfortunately" nao aparece
    colado em "interview" do mesmo jeito. A ordem em REGRAS E a prioridade, e o que importa
    num e-mail que tem as duas palavras e o desfecho."""
    estado, _ = G.classificar(
        "Retorno do Processo Seletivo\n"
        "Agradecemos sua participacao na entrevista. Infelizmente optamos por seguir com "
        "outros perfis neste momento.")
    assert estado == "rejeitada"


def test_convite_de_entrevista_continua_sendo_entrevista():
    """Contraprova do teste acima: consertar a rejeicao nao pode engolir o convite."""
    estado, _ = G.classificar(
        "Proximos passos\n"
        "Gostariamos de agendar uma entrevista com voce. Segue o link para escolher horario.")
    assert estado == "entrevista"


def test_rejeicao_em_ingles():
    estado, _ = G.classificar(
        "In regards to your application\n"
        "Unfortunately we have decided to move forward with other candidates.")
    assert estado == "rejeitada"


# --------------------------------------------------------- prioridades ----

def test_oferta_ganha_de_tudo():
    """A ordem em REGRAS E' a prioridade. Carta proposta e' o unico e-mail que muda a vida
    de quem procura vaga, entao nao pode perder para 'entrevista' num texto que tem as duas
    palavras."""
    estado, _ = G.classificar(
        "Carta Proposta Analista de Arquitetura\n"
        "Seu perfil foi aprovado. Em anexo o pacote de compensacao. "
        "Podemos agendar uma conversa para os proximos passos.")
    assert estado == "OFERTA"


def test_prazo_vence_antes_de_convite():
    estado, _ = G.classificar(
        "Final Reminder: Start your interview with TalentHQ\n"
        "You have been invited to a video interview.")
    assert estado == "EXPIRANDO"


def test_confirmacao_de_candidatura_nao_e_urgente():
    """Resposta automatica de 'recebemos sua candidatura' NAO pode disparar alerta.
    Aviso que toca demais vira aviso que ninguem le."""
    estado, acoes = G.classificar(
        "Thank you for applying to Kraken\n"
        "We have received your application and will review it shortly.")
    assert estado == "respondida"
    assert acoes == []


# ------------------------------------------------------------- acoes ----

def test_convite_sem_connects_vira_acao():
    _, acoes = G.classificar(
        "Invitation to Interview for: Marketing analysis and Growth\n"
        "You can apply to this opportunity for free, no Connects needed.")
    assert "CONVITE 0 CONNECTS" in acoes


def test_oferta_pede_acao_de_assinar():
    _, acoes = G.classificar("Carta Proposta\nEnvie seu aceite formal.")
    assert "ASSINAR/RESPONDER OFERTA" in acoes


# ------------------------------------------------------------- corpo ----

def test_texto_ignora_css_embutido():
    """O bug: um remetente mandava text/plain quase vazio e todo o conteudo em HTML com
    <style>. Sem remover o style, o classificador lia regra de CSS achando que era corpo."""
    msg = {"payload": {"mimeType": "text/html", "body": {}, "parts": [
        {"mimeType": "text/html", "body": {"data": _b64(
            "<html><head><style>.x{content:'interview'}</style></head>"
            "<body>Thank you for applying</body></html>")}}]}}
    saida = G.texto(msg)
    assert "Thank you for applying" in saida
    assert "content:" not in saida


def _b64(s):
    import base64
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii")
