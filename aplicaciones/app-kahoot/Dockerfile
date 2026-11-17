FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py preguntas.json .
COPY templates/ templates/
COPY static/ static/

# Puerto por defecto; se puede cambiar con APP_PORT en el .env
EXPOSE 8078

CMD ["python", "app.py"]
