# ChromaDB + ChromaDB UI con Docker Compose

Levanta **ChromaDB** (imagen oficial, base de datos vectorial) y **ChromaDB UI** (gestor web de terceros, equivalente a Redis Insight / pgAdmin).

## Servicios

| Servicio     | Imagen                                | Puerto | Acceso                |
|--------------|---------------------------------------|--------|-----------------------|
| chromadb     | `chromadb/chroma:1.5.3`               | 8000   | http://localhost:8000 |
| chromadb-ui  | se construye desde GitHub (BlackyDrum/chromadb-ui) | 8090 | http://localhost:8090 |

**Credenciales:** ninguna. Chroma 1.x no incluye autenticación; por eso los puertos solo se publican en `127.0.0.1` (únicamente tu equipo).

> ChromaDB UI **no es un proyecto oficial** de Chroma y solo funciona con la API v2.

## Requisitos

- Docker Desktop (macOS / Windows) o Docker Engine (Linux)
- Docker Compose v2 (viene incluido en Docker Desktop)
- Internet en el primer arranque (descarga la imagen y construye el gestor)

## Estructura

```
chroma-docker/
├── docker-compose.yml
├── chroma.docker.yaml   # configuración de Chroma (puerto, persistencia, CORS)
├── README.md
└── chroma_data/         # se crea solo: datos de Chroma
```

## Levantar

```bash
docker compose up -d --build
```

> La primera vez tarda unos minutos porque construye el gestor web.

Verificar que esté corriendo:

```bash
docker compose ps
```

Probar que Chroma responde:

```bash
curl http://localhost:8000/api/v2/heartbeat
```

## Conectarse desde la web (ChromaDB UI)

1. Abre http://localhost:8090
2. Completa la conexión:
   - **URL:** `http://localhost:8000`  ← aquí **sí** es `localhost`
   - **Tenant:** `default_tenant`
   - **Database:** `default_database`
3. Conectar

> A diferencia de Redis Insight, este gestor es una página que corre en **tu navegador** y llama a Chroma desde ahí, por eso se usa `localhost:8000` y no el nombre del servicio. Por la misma razón, Chroma debe permitir el origen `http://localhost:8090` (CORS), ya configurado en `chroma.docker.yaml`.

## Conectarse desde Python

```bash
pip install chromadb
```

```python
import chromadb

client = chromadb.HttpClient(host="localhost", port=8000)
print(client.heartbeat())

col = client.get_or_create_collection("autos")
col.add(
    ids=["1", "2", "3"],
    documents=["Porsche 911, auto deportivo", "Lavado de autos", "Ford Mustang, coupé deportivo"],
)

res = col.query(query_texts=["autos deportivos para pasear"], n_results=2)
print(res["documents"])
```

> La primera vez, Chroma descarga un modelo de embeddings pequeño para el cliente; puede tardar un poco.

## Conectarse desde otro contenedor

```
http://chromadb:8000
```

(el nombre del servicio, siempre el puerto interno `8000`)

## Comandos útiles

```bash
docker compose logs -f chromadb      # ver logs de Chroma
docker compose stop                  # detener
docker compose start                 # iniciar de nuevo
docker compose down                  # eliminar contenedores (los datos se conservan)
docker compose up -d --build         # reconstruir el gestor (trae la última versión)
rm -rf chroma_data                   # borrar los datos por completo
```

## Cambiar la versión de Chroma

Edita el tag de la imagen en `docker-compose.yml` (por ejemplo `chromadb/chroma:1.5.3`) y ejecuta:

```bash
docker compose down && docker compose up -d
```

> Mantén la versión fija para evitar incompatibilidades con el cliente de Python. Haz una copia de `chroma_data/` antes de actualizar.

## Seguridad

- Chroma 1.x **no tiene usuario ni contraseña**. No expongas el puerto 8000 a internet.
- Si necesitas acceso remoto, usa un proxy con autenticación (nginx, Traefik) o una VPN.
- Para permitir acceso desde otros equipos de la red, cambia `"127.0.0.1:8000:8000"` por `"8000:8000"` (solo en redes de confianza).

## Solución de problemas

- **El gestor dice "CORS" o "Network Error":** revisa que `cors_allow_origins` en `chroma.docker.yaml` incluya la URL desde la que abres el gestor, y reinicia: `docker compose restart chromadb`.
- **`docker compose ps` muestra `unhealthy`:** la prueba de salud usa `curl` dentro del contenedor. Si la imagen no lo incluye, elimina el bloque `healthcheck` (Chroma sigue funcionando; verifica con el `curl` desde tu equipo).
- **El gestor no construye:** necesita internet y Docker con BuildKit (incluido en Docker Desktop reciente). Prueba `docker compose build --no-cache chromadb-ui`.
- **Puerto ocupado:** cambia el lado izquierdo del puerto, por ejemplo `"127.0.0.1:8001:8000"`, y usa esa URL.

## Windows

- Usa Docker Desktop con backend **WSL2** (por defecto).
- Los comandos son los mismos (`docker compose ...`) en PowerShell, CMD o terminal WSL.
- Si el proyecto está en una carpeta de Windows (`C:\...`) y ves errores de permisos o lentitud con `./chroma_data`, mueve el proyecto al sistema de archivos de WSL (`\\wsl$\Ubuntu\home\tu_usuario\`) o usa un volumen con nombre (ver abajo).
- Asegúrate de que `docker-compose.yml` y `chroma.docker.yaml` usen saltos de línea LF.

### Alternativa con volumen con nombre (sin carpeta local)

```yaml
services:
  chromadb:
    volumes:
      - chroma_data:/data
      - ./chroma.docker.yaml:/chroma/config.yaml:ro

volumes:
  chroma_data:
```

## Linux

Si da error de permisos en `./chroma_data`, crea la carpeta antes y ajusta sus permisos:

```bash
mkdir -p chroma_data && sudo chown -R $USER:$USER chroma_data
```