"""Conexao com o Supabase pessoal. Le a URL do .env do repo AIOS, nunca de literal.

GOTCHA conhecido do projeto: o pooler do Supabase mudou de `aws-0` pra `aws-1` e a string
velha da' `tenant or user not found`, que parece senha errada. Se der isso, e' host, nao
credencial. Ver memoria `gotcha-supabase-pooler-aws0-aws1`.
"""
import os, io, re

ENV = os.environ.get("ENV_FILE", ".env")
CHAVE = "SUPABASE_PESSOAL_DB_URL"


def url():
    u = os.environ.get(CHAVE)
    if u:
        return u
    if not os.path.exists(ENV):
        raise SystemExit("nao achei %s e %s nao esta no ambiente" % (ENV, CHAVE))
    for linha in io.open(ENV, encoding="utf-8", errors="replace"):
        linha = linha.strip()
        if linha.startswith(CHAVE + "="):
            v = linha.split("=", 1)[1].strip().strip('"').strip("'")
            if v:
                return v
    raise SystemExit("%s existe no arquivo mas esta vazio" % CHAVE)


def conectar():
    import psycopg2
    u = url()
    try:
        return psycopg2.connect(u, connect_timeout=20)
    except Exception as e:
        m = str(e)
        if "tenant or user not found" in m.lower():
            raise SystemExit(
                "pooler recusou: 'tenant or user not found'.\n"
                "Isto quase sempre e' HOST errado, nao senha: o pooler do Supabase migrou "
                "de aws-0 pra aws-1. Confere o host em %s." % ENV)
        raise


def esconder(u=None):
    """Versao da string segura pra imprimir em log."""
    u = u or url()
    return re.sub(r"://([^:]+):([^@]+)@", lambda m: "://%s:***@" % m.group(1), u)


if __name__ == "__main__":
    c = conectar()
    cur = c.cursor()
    cur.execute("select current_database(), current_user, version()")
    d, usr, v = cur.fetchone()
    print("conectado:", esconder())
    print("banco    :", d)
    print("usuario  :", usr)
    print("versao   :", v.split(",")[0])
    c.close()
