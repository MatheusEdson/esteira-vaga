FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY core/ ./core/
COPY perfil.example.json .
# data/ NAO entra na imagem: e' volume, e' dado do usuario
VOLUME ["/app/data"]
EXPOSE 8099
CMD ["uvicorn","app.api.main:app","--host","0.0.0.0","--port","8099"]
