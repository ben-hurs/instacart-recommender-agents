# Imagem do Python que roda o código do projeto (src/, tests/).
# Roda num Linux dentro do Docker, então não sofre com o bloqueio de DLLs
# do Windows e é igual em qualquer máquina.

FROM python:3.12-slim

# Não gerar arquivos .pyc e mostrar os prints na hora (sem buffer).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copiamos SÓ o requirements.txt primeiro: enquanto ele não mudar, o Docker
# reaproveita a camada já instalada (cache) e o build fica rápido.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# O código NÃO é copiado para a imagem: o docker-compose monta a pasta do
# projeto em /app, então qualquer edição no VS Code vale na hora.

CMD ["python", "-m", "src.db"]
