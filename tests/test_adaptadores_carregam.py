# -*- coding: utf-8 -*-
"""Todo adaptador carrega sem erro de programação.

POR QUE ESTE É O TESTE MAIS IMPORTANTE DO REPO. Os 16 adaptadores já ficaram 100% mortos
com `FileNotFoundError`, e a suíte seguia verde: `compileall` passa, `pyflakes` passa,
`pytest` passa, e nada funciona. Um caminho errado só falha quando alguém executa.

Depois, a extração do `core/bootstrap.py` quebrou 5 deles de novo, com um `TypeError` de
assinatura que `pyflakes` também não pega, porque só aparece na chamada.

Este teste importa cada adaptador com o navegador substituído por um dublê. Erro de
programação (NameError, TypeError, AttributeError, ImportError) reprova. `SystemExit` é
aprovação: significa que o adaptador chegou até a validação e parou porque falta um dado,
que é exatamente o comportamento desejado.

Rodar:  python -m pytest tests/ -q
"""
import importlib.util
import re
import io
import os
import sys
import contextlib

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

ADAPTERS = sorted(
    os.path.join("adapters", a)
    for a in os.listdir(os.path.join(RAIZ, "adapters"))
    if a.startswith("aplicar_") and a.endswith(".py")
) + [os.path.join("core", "preencher_workable.py")]

PERFIL = os.path.join(RAIZ, "data", "perfil.json")


class _NavegadorProibido(Exception):
    """Sentinela. Se um adaptador chegar aqui, ele passou de toda a fase de carga."""


def _dublê(*a, **kw):
    raise _NavegadorProibido()


@pytest.mark.skipif(not os.path.exists(PERFIL),
                    reason="precisa de data/perfil.json (copie de perfil.example.json)")
@pytest.mark.parametrize("caminho", ADAPTERS, ids=lambda p: os.path.basename(p))
def test_adaptador_carrega(caminho, monkeypatch):
    import nav
    monkeypatch.setattr(nav, "sync_playwright", _dublê)
    monkeypatch.setattr(sys, "argv", ["x", "https://exemplo.invalido/vaga/1"])

    spec = importlib.util.spec_from_file_location("_ad", os.path.join(RAIZ, caminho))
    mod = importlib.util.module_from_spec(spec)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            spec.loader.exec_module(mod)
    except (_NavegadorProibido, SystemExit):
        pass                      # chegou ao navegador, ou parou por dado faltando: ok
    except (NameError, TypeError, AttributeError, ImportError) as e:
        pytest.fail("%s tem erro de programacao: %s: %s"
                    % (caminho, type(e).__name__, str(e)[:200]))
    except Exception:
        pass                      # rede, timeout, seletor: nao e o que este teste cobre


def test_todo_adaptador_usa_o_bootstrap():
    """Nenhum adaptador deve voltar a montar o caminho do perfil na mão.

    Era assim que os 16 apontavam para `adapters/perfil.json`, um arquivo que nunca
    existiu, num caminho que o `.gitignore` não cobria.
    """
    reincidentes = []
    for caminho in ADAPTERS:
        with open(os.path.join(RAIZ, caminho), encoding="utf-8") as f:
            txt = f.read()
        # So' interessa a CONSTRUCAO do caminho, nao mencao em comentario ou mensagem de
        # erro: varias dizem "preencha data/perfil.json", e devem mesmo dizer.
        monta_na_mao = re.search(r"join\([^)]*BASE[^)]*perfil\.json", txt)
        abre_direto = re.search(r"open\(\s*[\"'][^\"']*perfil\.json", txt)
        if monta_na_mao or abre_direto:
            reincidentes.append(caminho)
    assert not reincidentes, "voltou a montar caminho de perfil na mao: %s" % reincidentes
