FROM python:3.12-slim

WORKDIR /app

# 1. Copiar PRIMERO requirements.txt
COPY requirements.txt .

# 2. Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copiar el código
COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]