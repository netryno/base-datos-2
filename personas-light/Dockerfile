FROM python:3.12-slim

WORKDIR /app

# 1. Copiar PRIMERO requirements.txt
COPY requirements.txt .

# 2. Instalar dependencias
# sqlite3 ya viene incluido en la imagen oficial de Python (módulo estándar).
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copiar el código
COPY app/ ./app/

# 4. Crear el directorio donde vivirá el archivo SQLite (lo monta docker-compose)
RUN mkdir -p /app/data

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
