# -*- coding: utf-8 -*-
"""Testes de que os caminhos de arquivo resolvem.

Estes existem por causa de uma falha especifica: os 16 adaptadores montavam
`adapters/cv-*.pdf` enquanto os curriculos vivem em `curriculos/`. Ficaram 100% mortos
com FileNotFoundError, e a suite continuou verde o tempo todo, porque um os.path.join so'
falha em runtime. compileall passa, pyflakes passa, pytest passa, e nada funciona.

Um teste que percorre o perfil e afirma que cada arquivo existe pega essa classe inteira.

Rodar:  python -m pytest tests/ -q
"""
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

PERFIL = os.path.join(RAIZ, "data", "perfil.json")
sem_perfil = pytest.mark.skipif(
    not os.path.exists(PERFIL),
    reason="precisa de data/perfil.json (copie de perfil.example.json)")


@sem_perfil
def test_todo_curriculo_declarado_existe():
    from core.perfil import perfil, curriculo
    faltando = []
    for trilha, nome in (perfil().get("curriculos") or {}).items():
        if not nome or trilha.startswith("_"):
            continue
        try:
            curriculo(trilha)
        except SystemExit:
            faltando.append("%s -> %s" % (trilha, nome))
    assert not faltando, "curriculo declarado no perfil e ausente no disco: %s" % faltando


@sem_perfil
def test_todo_anexo_de_arquivo_existe():
    """URL passa direto; nome de arquivo tem que existir."""
    from core.perfil import perfil, anexo
    faltando = []
    for chave, valor in (perfil().get("anexos") or {}).items():
        if not valor or chave.startswith("_") or str(valor).startswith("http"):
            continue
        try:
            anexo(chave)
        except SystemExit:
            faltando.append("%s -> %s" % (chave, valor))
    assert not faltando, "anexo declarado no perfil e ausente no disco: %s" % faltando


def test_curriculo_ausente_aborta_com_caminho_na_mensagem():
    """A mensagem precisa dizer ONDE procurou. A versao antiga estourava um
    FileNotFoundError cru apontando para adapters/, que e' o lugar errado, e mandava a
    pessoa criar o arquivo la."""
    from core.perfil import _exigir
    with pytest.raises(SystemExit) as e:
        _exigir(os.path.join(RAIZ, "curriculos", "nao-existe-mesmo.pdf"), "curriculo")
    assert "curriculos" in str(e.value)
    assert "nao-existe-mesmo.pdf" in str(e.value)


def test_perfil_example_cobre_as_chaves_que_o_codigo_exige():
    """Toda chave pedida por do_perfil() nos adaptadores precisa existir no exemplo,
    senao quem clona descobre uma a uma, uma candidatura por vez."""
    import json
    import glob
    import re
    with open(os.path.join(RAIZ, "perfil.example.json"), encoding="utf-8") as f:
        ex = json.load(f)
    pedidas = set()
    for p in glob.glob(os.path.join(RAIZ, "adapters", "*.py")) + \
             glob.glob(os.path.join(RAIZ, "core", "*.py")):
        with open(p, encoding="utf-8") as f:
            pedidas |= set(re.findall(r'do_perfil\("([^"]+)"', f.read()))
    faltando = sorted(k for k in pedidas if k not in ex["respostas_padrao"])
    assert not faltando, "chave usada no codigo e ausente do perfil.example.json: %s" % faltando
