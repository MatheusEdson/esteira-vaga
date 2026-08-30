# 3.10 e' o piso que o CI testa. Fixar aqui evita a imagem passar e o CI reprovar (ou o
# contrario) por diferenca de versao que ninguem percebe.
FROM python:3.10-slim

WORKDIR /app

# So' as dependencias da API, nao o requirements.txt inteiro. A imagem copia apenas app/ e
# core/, entao instalar tudo puxava o patchright (que baixa um Chromium), o psycopg2 e o
# cliente completo da API do Google para dentro de um container que nao abre navegador,
# nao fala com Postgres e nao le Gmail.
COPY requirements-app.txt .
RUN pip install --no-cache-dir -r requirements-app.txt

COPY app/ ./app/
COPY core/ ./core/
COPY perfil.example.json .

# data/ NAO entra na imagem: e' volume, e' dado do usuario.
VOLUME ["/app/data"]
EXPOSE 8099

# Sem healthcheck, um processo que subiu mas nao serve mais fica "running" para sempre e
# o restart automatico nunca dispara.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8099/api/stats', timeout=2).status == 200 else 1)"

CMD ["uvicorn","app.api.main:app","--host","0.0.0.0","--port","8099"]
