FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# PyTorch usa OpenMP.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py datos.py servicio.py .
COPY templates/ templates/
COPY static/ static/
COPY scripts/ scripts/

EXPOSE 8120

CMD ["python", "app.py"]
