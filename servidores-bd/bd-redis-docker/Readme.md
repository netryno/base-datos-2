# Redis + Redis Insight con Docker Compose

Levanta **Redis** (imagen oficial) y **Redis Insight** (gestor web oficial de Redis, equivalente a pgAdmin).

## Servicios

| Servicio       | Imagen                    | Puerto | Acceso                  |
|----------------|---------------------------|--------|-------------------------|
| redis          | `redis:8`                 | 6379   | `localhost:6379`        |
| redisinsight   | `redis/redisinsight`      | 5540   | http://localhost:5540   |

**Credenciales de Redis:** contraseña `123456` (usuario por defecto: `default`).

## Requisitos

- Docker Desktop (macOS / Windows) o Docker Engine (Linux)
- Docker Compose v2 (viene incluido en Docker Desktop)

## Estructura

```
redis-docker/
├── docker-compose.yml
├── README.md
├── redis_data/          # se crea solo: datolss de Redis
└── redisinsight_data/   # se crea solo: configuración de Redis Insight
```

## Levantar

```bash
docker compose up -d
```

Verificar que esté corriendo:

```bash
docker compose ps
```

## Conectarse desde la web (Redis Insight)

1. Abre http://localhost:5540
2. Clic en **Add Redis database** → **Connection Settings**
3. Completa:
   - **Host:** `redis`  ← nombre del servicio, **no** `localhost`
   - **Port:** `6379`
   - **Username:** (vacío o `default`)
   - **Password:** `123456`
4. **Add Redis Database**

> Dentro de Docker, los contenedores se ven por el nombre del servicio. `localhost` desde Redis Insight apuntaría al propio contenedor de Redis Insight.

## Conectarse desde la terminal

```bash
docker exec -it redis-d redis-cli -a 123456
```

Pruebas rápidas:

```
127.0.0.1:6379> PING
PONG
127.0.0.1:6379> SET saludo "hola redis"
OK
127.0.0.1:6379> GET saludo
"hola redis"
```

## Conectarse desde una aplicación

```
redis://default:123456@localhost:6379
```

## Comandos útiles

```bash
docker compose logs -f redis     # ver logs
docker compose stop              # detener
docker compose start             # iniciar de nuevo
docker compose down              # eliminar contenedores (los datos se conservan)
docker compose down -v           # idem + volúmenes anónimos
rm -rf redis_data redisinsight_data   # borrar datos por completo
```

## Cambiar la contraseña

Hay que cambiarla en **dos lugares** del `docker-compose.yml`: el `command` y el `healthcheck`. Luego:

```bash
docker compose down && docker compose up -d
```

## Windows

- Usa Docker Desktop con backend **WSL2** (por defecto).
- Los comandos son los mismos (`docker compose ...`) en PowerShell, CMD o terminal WSL.
- Si el proyecto está en una carpeta de Windows (`C:\...`) y ves errores de permisos o lentitud con `./redis_data`, mueve el proyecto al sistema de archivos de WSL (`\\wsl$\Ubuntu\home\tu_usuario\`) o usa volúmenes con nombre (ver abajo).
- Asegúrate de que `docker-compose.yml` use saltos de línea LF y no tenga caracteres raros al copiarlo.

### Alternativa con volúmenes con nombre (sin carpetas locales)

```yaml
services:
  redis:
    volumes:
      - redis_data:/data
  redisinsight:
    volumes:
      - redisinsight_data:/data

volumes:
  redis_data:
  redisinsight_data:
```

## Linux

Redis Insight corre con el usuario `1000`. Si da error de permisos en `./redisinsight_data`:

```bash
mkdir -p redisinsight_data && sudo chown -R 1000:1000 redisinsight_data
```