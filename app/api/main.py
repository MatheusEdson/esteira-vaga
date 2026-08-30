"""API da esteira. Serve o Kanban e le/escreve os JSON de data/.

Um processo so' entrega front e API, de proposito: quem clona o repo roda um comando
e esta' no ar, sem build de front, sem docker obrigatorio, sem banco.

    uvicorn app.api.main:app --host 127.0.0.1 --port 8099

Nao ha autenticacao aqui. Cada instancia e' de UMA pessoa. Em producao o gate e' o
nginx na frente (ver deploy/nginx.conf: gate por ?key=). Nunca exponha esta porta
direto na internet.
"""
from __future__ import annotations
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi import (FastAPI, HTTPException, Body, UploadFile,        # noqa: E402
                     File, Form)
from fastapi.responses import FileResponse, JSONResponse              # noqa: E402
from fastapi.staticfiles import StaticFiles                           # noqa: E402

from core import store                                               # noqa: E402
from core.estados import COLUNAS, ESTADOS, valido                    # noqa: E402

WEB = RAIZ / "app" / "web"

app = FastAPI(title="Esteira de Vagas", version="1.0.0", docs_url="/api/docs")


# ------------------------------------------------------------------ leitura
@app.get("/api/quadro")
def quadro():
    """Tudo que o Kanban precisa numa chamada: colunas, cartoes e metricas."""
    agrupado = store.por_estado()
    return {
        "colunas": [{"id": e, "rotulo": r, "ajuda": a} for e, r, a in COLUNAS],
        "vagas": agrupado,
        "stats": store.estatisticas(),
    }


@app.get("/api/vagas/{vaga_id}")
def uma(vaga_id: str):
    v = next((x for x in store.listar() if x.get("id") == vaga_id), None)
    if v is None:
        raise HTTPException(404, "vaga nao encontrada")
    return {"vaga": v, "transicoes": store.transicoes(vaga_id)}


@app.get("/api/perfil")
def perfil():
    """Perfil sem os campos sensiveis: o front nao precisa de CPF nem de senha."""
    p = store.perfil()
    ident = dict(p.get("identidade", {}))
    for k in ("cpf", "_cpf_nota", "contato_emergencia"):
        ident.pop(k, None)
    return {
        "identidade": ident,
        "respostas_padrao": p.get("respostas_padrao", {}),
        "NUNCA_AFIRMAR": p.get("NUNCA_AFIRMAR", {}),
        "curriculos": p.get("curriculos", {}),
        "anexos": p.get("anexos", {}),
        "corte_auto_envio": p.get("corte_auto_envio", {}),
    }


@app.get("/api/stats")
def stats():
    return store.estatisticas()


# ------------------------------------------------------- perfil: editar e subir
CAMPOS_SENSIVEIS = {"cpf", "contato_emergencia"}


@app.put("/api/perfil")
def salvar_perfil(corpo: dict = Body(...)):
    """Grava as secoes editaveis. Campo sensivel so' e' sobrescrito se vier valor:
    assim o front pode nunca ler CPF e ainda assim salvar o resto sem apagar o CPF."""
    p = store.perfil()
    for secao in ("identidade", "respostas_padrao", "NUNCA_AFIRMAR", "curriculos", "anexos"):
        entrada = corpo.get(secao)
        if not isinstance(entrada, dict):
            continue
        atual = p.setdefault(secao, {})
        for k, v in entrada.items():
            if secao == "identidade" and k in CAMPOS_SENSIVEIS and (v is None or v == ""):
                continue        # nao apaga o que o front nunca viu
            atual[k] = v
    store.salvar_perfil(p)
    return {"ok": True}


@app.post("/api/upload")
async def upload(tipo: str = Form(...), chave: str = Form(""), arquivo: UploadFile = File(...)):
    """Sobe curriculo ou anexo e, se vier `chave`, ja aponta o perfil para ele."""
    try:
        destino, nome = store.salvar_arquivo(tipo, arquivo.filename, await arquivo.read())
    except ValueError as e:
        raise HTTPException(400, str(e))
    if chave:
        p = store.perfil()
        secao = "curriculos" if tipo == "curriculo" else "anexos"
        p.setdefault(secao, {})[chave] = nome
        store.salvar_perfil(p)
    return {"arquivo": nome, "caminho": destino, "chave": chave or None}


@app.get("/api/arquivos")
def arquivos():
    return store.listar_arquivos()


@app.delete("/api/arquivos/{tipo}/{nome}")
def remover_arquivo(tipo: str, nome: str):
    try:
        store.remover_arquivo(tipo, nome)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


# ------------------------------------------------------------------ escrita
@app.post("/api/vagas")
def criar(corpo: dict = Body(...)):
    url = (corpo.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "url obrigatoria")
    if not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "url precisa comecar com http:// ou https://")
    r = store.adicionar(url,
                        empresa=corpo.get("empresa", ""),
                        titulo=corpo.get("titulo", ""),
                        ats=corpo.get("ats", ""))
    if r.get("duplicada"):
        # 409, nao 400: nao e' erro do usuario, e' guarda contra enviar duas vezes
        return JSONResponse(status_code=409,
                            content={"erro": "url ja existe no quadro",
                                     "vaga": r["vaga"]})
    return {"vaga": r["vaga"]}


@app.patch("/api/vagas/{vaga_id}/estado")
def mover(vaga_id: str, corpo: dict = Body(...)):
    novo = (corpo.get("estado") or "").strip()
    if not valido(novo):
        raise HTTPException(400, "estado invalido. use um de: %s" % ", ".join(ESTADOS))
    try:
        return {"vaga": store.mover(vaga_id, novo, nota=corpo.get("nota"))}
    except KeyError:
        raise HTTPException(404, "vaga nao encontrada")


@app.patch("/api/vagas/{vaga_id}")
def editar(vaga_id: str, corpo: dict = Body(...)):
    try:
        return {"vaga": store.atualizar(vaga_id, corpo)}
    except KeyError:
        raise HTTPException(404, "vaga nao encontrada")


# ------------------------------------------------------------------ front
@app.get("/")
def raiz():
    return FileResponse(WEB / "index.html")


if WEB.exists():
    app.mount("/static", StaticFiles(directory=str(WEB)), name="static")
