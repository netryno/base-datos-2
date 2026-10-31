# Buscador entre idiomas · ChromaDB

Demo de Base de Datos II. La misma consulta se busca de dos formas: texto exacto (como `ILIKE`) y por significado, con vectores en Chroma.

Chroma tiene que estar en marcha (proyecto `bd-chroma`, puerto **8000**, imagen 1.5.3). El cliente Python es 1.5.9, de la misma línea. Esta app usa el puerto **8120**.

## Puesta en marcha

Python 3.10 o superior.

```bash
cp .env.example .env          # si todavía no existe
pip install -r requirements.txt
python scripts/precargar_modelo.py
python app.py
```

Abrir <http://localhost:8120> y pulsar **Cargar datos** (148 registros).

Con Docker, Chroma se alcanza por `host.docker.internal`:

```bash
docker compose up --build
```

La primera vez el modelo `paraphrase-multilingual-MiniLM-L12-v2` se descarga desde Hugging Face (cientos de MB).

Antes de la clase, sin abrir el navegador:

```bash
python scripts/verificar.py
```

El guion de la clase está en `INSTRUCCIONES.md`.

## Estructura

```
app.py            Flask: página y API
datos.py          Palabras y frases del demo
servicio.py       Cliente Chroma, carga y las dos búsquedas
templates/        Página del buscador
static/           Estilos y lógica de la interfaz
scripts/          Precarga del modelo y verificación
```
