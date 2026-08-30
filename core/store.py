"""Acesso a dados da esteira. Fonte da verdade: os JSON em data/.

Por que JSON e nao banco: os 16 adaptadores em adapters/ leem `perfil.json` e escrevem
`enviadas.json` direto do disco. Trocar por SQLite exigiria mexer nos 16. Para instancia
de uma pessoa so', arquivo resolve, e tem um beneficio real: `enviadas.json` versionado
no git do proprio usuario da historico de candidatura de graca.

O que este modulo garante:
  - escrita ATOMICA (tmp + os.replace), para o app web e a esteira nunca se atropelarem
  - lock de arquivo, porque a esteira roda 2x por semana e pode coincidir com o app
  - migracao idempotente do `status` texto-livre para `estado` + `status_detalhe`
  - livro-caixa append-only de transicoes, separado do estado atual

Caminho para SQLite, se um dia a concorrencia doer: trocar `_ler`/`_escrever` por
consultas e manter a mesma interface publica. Nada fora deste modulo sabe que e' JSON.
"""
from __future__ import annotations
import json, os, re, time, uuid, tempfile
from datetime import datetime, timezone
from pathlib import Path

from .estados import classificar, valido, ESTADOS

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "data"
VAGAS = DADOS / "enviadas.json"
PERFIL = DADOS / "perfil.json"
LEDGER = DADOS / "transicoes.jsonl"
LOCK = DADOS / ".lock"


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Lock:
    """Lock por diretorio: mkdir e' atomico em qualquer sistema de arquivo."""

    def __init__(self, alvo: Path = LOCK, timeout: float = 10.0):
        self.alvo, self.timeout = alvo, timeout

    def __enter__(self):
        limite = time.time() + self.timeout
        while True:
            try:
                self.alvo.mkdir(parents=False, exist_ok=False)
                return self
            except FileExistsError:
                # lock velho (>60s) e' considerado orfao: processo morreu no meio
                try:
                    if time.time() - self.alvo.stat().st_mtime > 60:
                        self.alvo.rmdir()
                        continue
                except OSError:
                    pass
                if time.time() > limite:
                    raise TimeoutError("lock de dados ocupado: %s" % self.alvo)
                time.sleep(0.15)

    def __exit__(self, *_):
        try:
            self.alvo.rmdir()
        except OSError:
            pass


def _ler(caminho: Path, default):
    if not caminho.exists():
        return default
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def _escrever(caminho: Path, dados) -> None:
    """Escrita atomica: grava em tmp no MESMO diretorio e troca por rename."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(caminho.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, caminho)      # atomico
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ----------------------------------------------------------------- migracao
def migrar(vagas: list[dict]) -> tuple[list[dict], int]:
    """Garante `estado`, `status_detalhe` e `id` em todo registro. Idempotente."""
    mudou = 0
    vistos = set()
    for v in vagas:
        if not v.get("id"):
            base = (v.get("empresa") or "vaga").lower()
            base = "".join(c if c.isalnum() else "-" for c in base).strip("-")[:40]
            v["id"] = "%s-%s" % (base, uuid.uuid4().hex[:6])
            mudou += 1
        # id duplicado quebra o Kanban (dois cartoes com a mesma chave)
        if v["id"] in vistos:
            v["id"] = "%s-%s" % (v["id"], uuid.uuid4().hex[:4])
            mudou += 1
        vistos.add(v["id"])

        if not v.get("estado"):
            v["estado"] = classificar(v.get("status"))
            mudou += 1
        if v.get("status") and not v.get("status_detalhe"):
            # preserva o texto original inteiro: e' a prova de envio
            v["status_detalhe"] = v["status"]
            mudou += 1
        v.setdefault("criado_em", v.get("data") or agora()[:10])
    return vagas, mudou


# ----------------------------------------------------------------- leitura
def listar() -> list[dict]:
    vagas = _ler(VAGAS, [])
    vagas, mudou = migrar(vagas)
    if mudou:
        with Lock():
            _escrever(VAGAS, vagas)
    return vagas


def perfil() -> dict:
    return _ler(PERFIL, {})


def por_estado() -> dict[str, list[dict]]:
    out = {e: [] for e in ESTADOS}
    for v in listar():
        out.setdefault(v.get("estado", "descoberta"), []).append(v)
    return out


def estatisticas() -> dict:
    vagas = listar()
    cont = {e: 0 for e in ESTADOS}
    for v in vagas:
        cont[v.get("estado", "descoberta")] = cont.get(v.get("estado", "descoberta"), 0) + 1
    # "enviada" aqui e' cumulativo: quem chegou em entrevista ou proposta tambem foi enviada.
    depois_do_envio = ("respondida", "entrevista", "proposta", "rejeitada")
    enviadas = cont["enviada"] + sum(cont[e] for e in depois_do_envio)
    respostas = sum(cont[e] for e in depois_do_envio)
    avancadas = cont["entrevista"] + cont["proposta"]
    return {
        "total": len(vagas),
        "por_estado": cont,
        "enviadas": enviadas,
        "respostas": respostas,
        "taxa_resposta": round(100 * respostas / enviadas, 1) if enviadas else 0.0,
        "avancadas": avancadas,
        "taxa_avanco": round(100 * avancadas / enviadas, 1) if enviadas else 0.0,
        "propostas": cont["proposta"],
        "vivas": sum(cont[e] for e in ("descoberta", "fila", "enviada",
                                       "respondida", "entrevista", "proposta")),
    }


# ----------------------------------------------------------------- escrita
def _ledger(registro: dict) -> None:
    """Append-only. Estado atual fica na vaga; QUANDO mudou fica aqui."""
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def mover(vaga_id: str, novo_estado: str, nota: str | None = None) -> dict:
    if not valido(novo_estado):
        raise ValueError("estado invalido: %s" % novo_estado)
    with Lock():
        vagas = _ler(VAGAS, [])
        vagas, _ = migrar(vagas)
        alvo = next((v for v in vagas if v.get("id") == vaga_id), None)
        if alvo is None:
            raise KeyError("vaga nao encontrada: %s" % vaga_id)
        antigo = alvo.get("estado")
        if antigo == novo_estado and not nota:
            return alvo
        alvo["estado"] = novo_estado
        alvo["atualizado_em"] = agora()
        if nota:
            alvo["status_detalhe"] = nota
        _escrever(VAGAS, vagas)
    _ledger({"em": agora(), "vaga": vaga_id, "de": antigo, "para": novo_estado, "nota": nota})
    return alvo


def adicionar(url: str, empresa: str = "", titulo: str = "",
              ats: str = "", extra: dict | None = None) -> dict:
    """Entrada do app: cola a URL, nasce um cartao em Descoberta."""
    url = (url or "").strip()
    if not url:
        raise ValueError("url vazia")
    with Lock():
        vagas = _ler(VAGAS, [])
        vagas, _ = migrar(vagas)
        ja = next((v for v in vagas if (v.get("url") or "").strip() == url), None)
        if ja:
            # duplicata e' erro caro: enviar duas vezes ao mesmo recrutador queima reputacao
            return {"duplicada": True, "vaga": ja}
        base = (empresa or "vaga").lower()
        base = "".join(c if c.isalnum() else "-" for c in base).strip("-")[:40] or "vaga"
        nova = {
            "id": "%s-%s" % (base, uuid.uuid4().hex[:6]),
            "url": url,
            "empresa": empresa or "(a identificar)",
            "titulo": titulo or "(a identificar)",
            "ats": ats or "",
            "data": agora()[:10],
            "criado_em": agora(),
            "estado": "descoberta",
            "status": "",
            "status_detalhe": "",
        }
        if extra:
            nova.update({k: v for k, v in extra.items() if k not in nova})
        vagas.append(nova)
        _escrever(VAGAS, vagas)
    _ledger({"em": agora(), "vaga": nova["id"], "de": None,
             "para": "descoberta", "nota": "adicionada pelo app"})
    return {"duplicada": False, "vaga": nova}


def atualizar(vaga_id: str, campos: dict) -> dict:
    """Edita campos livres. `estado` so' por mover(), para o ledger nao ter buraco."""
    proibidos = {"id", "estado"}
    with Lock():
        vagas = _ler(VAGAS, [])
        vagas, _ = migrar(vagas)
        alvo = next((v for v in vagas if v.get("id") == vaga_id), None)
        if alvo is None:
            raise KeyError("vaga nao encontrada: %s" % vaga_id)
        for k, v in campos.items():
            if k not in proibidos:
                alvo[k] = v
        alvo["atualizado_em"] = agora()
        _escrever(VAGAS, vagas)
    return alvo


def transicoes(vaga_id: str | None = None) -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    with open(LEDGER, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha:
                continue
            try:
                r = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if vaga_id is None or r.get("vaga") == vaga_id:
                out.append(r)
    return out


# ----------------------------------------------------------------- perfil e arquivos
CURRICULOS = RAIZ / "curriculos"
ANEXOS = RAIZ / "anexos"

# Whitelist de extensao. Sem isto, um campo de upload num app sem autenticacao aceita
# .html ou .svg e vira vetor de XSS armazenado, ou .py e vira execucao se algo importar.
EXT_OK = {
    "curriculo": {".pdf", ".doc", ".docx"},
    "anexo": {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".doc", ".docx"},
}
MAX_BYTES = 8 * 1024 * 1024


def salvar_perfil(p: dict) -> None:
    with Lock():
        _escrever(PERFIL, p)
    try:                       # o modulo core.perfil cacheia; invalida para refletir na hora
        from . import perfil as _P
        _P._bruto.cache_clear()
    except Exception:
        pass


def _pasta(tipo: str) -> Path:
    if tipo == "curriculo":
        return CURRICULOS
    if tipo == "anexo":
        return ANEXOS
    raise ValueError("tipo invalido: use 'curriculo' ou 'anexo'")


def _nome_seguro(nome: str) -> str:
    """So' o basename, so' caractere previsivel. Barra e '..' fora, senao e' path traversal."""
    base = os.path.basename((nome or "").replace("\\", "/")).strip()
    base = re.sub(r"[^A-Za-z0-9._-]", "-", base).strip("-.") or "arquivo"
    return base[:120]


def salvar_arquivo(tipo: str, nome: str, conteudo: bytes) -> tuple[str, str]:
    pasta = _pasta(tipo)
    if len(conteudo) > MAX_BYTES:
        raise ValueError("arquivo maior que %d MB" % (MAX_BYTES // (1024 * 1024)))
    seguro = _nome_seguro(nome)
    ext = os.path.splitext(seguro)[1].lower()
    if ext not in EXT_OK[tipo]:
        raise ValueError("extensao %s nao permitida para %s. Aceitas: %s"
                         % (ext or "(sem)", tipo, ", ".join(sorted(EXT_OK[tipo]))))
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / seguro
    fd, tmp = tempfile.mkstemp(dir=str(pasta), prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(conteudo)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, destino)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return str(destino), seguro


def listar_arquivos() -> dict:
    out = {}
    for tipo, pasta in (("curriculo", CURRICULOS), ("anexo", ANEXOS)):
        itens = []
        if pasta.exists():
            for p in sorted(pasta.iterdir()):
                if p.is_file() and not p.name.startswith("."):
                    itens.append({"nome": p.name, "kb": round(p.stat().st_size / 1024, 1)})
        out[tipo] = itens
    return out


def remover_arquivo(tipo: str, nome: str) -> None:
    alvo = _pasta(tipo) / _nome_seguro(nome)
    if not alvo.exists():
        raise FileNotFoundError("nao achei %s" % alvo.name)
    alvo.unlink()
