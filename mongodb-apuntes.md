# Personas + MongoDB (FastAPI)

Monolito educativo: API REST en Python sobre **MongoDB ya existente** (contenedor `mongo` de `servidores-bd/bd-mongo`). CRUD de personas y viajes con PyMongo.

## Requisitos

- Docker
- Stack MongoDB en marcha (`mongo`, puerto 27017 en el host)
- Red Docker compartida (p. ej. `bd-mongo_default`)

Compass / Compooss: `mongodb://admin:123456@localhost:27017` (host) · `mongodb://admin:123456@mongo:27017` (red Docker).

## Configuración

```bash
cp .env.example .env
# Ajusta DOCKER_MONGO_NETWORK si tu red tiene otro nombre
```

| Variable | Uso |
|----------|-----|
| `API_HOST_PORT` | Puerto de la API (default `8075`) |
| `DOCKER_MONGO_NETWORK` | Red del compose de `bd-mongo` |
| `MONGO_HOST` | `mongo` en Docker; `localhost` fuera de Docker |
| `DB_NAME` | Base lógica (colecciones `paises`, `personas`, `viajes`) |

## Arranque

```bash
docker compose up --build
```

Al **startup**: ping a MongoDB, crea `DB_NAME` y colecciones si faltan, índices (único en `ci`, refs en viajes) y semilla de `paises` si está vacía. IDs numéricos (`persona_id`, `viaje_id`) vía colección `counters`.

- API: http://localhost:8075  
- Docs: http://localhost:8075/docs  

## Modelo (documentos)

Equivalente al ER relacional: catálogo `paises`, `personas`, `viajes` con `persona_id` y `pais_id`. Borrar persona elimina sus viajes en aplicación (CASCADE).

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Resumen y ayuda Excel |
| POST | `/by-paul/personas` | Crear persona |
| POST | `/by-paul/personas/import-excel` | Importar `.xlsx` |
| GET | `/by-paul/personas` | Listar personas |
| DELETE | `/by-paul/personas/{id}` | Eliminar persona + viajes |
| POST | `/by-paul/viajes` | Crear viaje |
| GET | `/by-paul/viajes` | Listar viajes (`$lookup`) |

## Estructura

```
app/main.py               # API monolítica
app/database_bootstrap.py # BD, colecciones, índices, semilla
docker-compose.yml        # Solo api + red externa
.env.example
```

## Stack

Python 3.12 · FastAPI · Uvicorn · pymongo · openpyxl
