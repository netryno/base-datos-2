# Mongo + Redis · Caché, Pub/Sub y Lock

Demo para la materia Base de Datos II. Una página web con **tres widgets**
que muestran cómo Redis complementa a MongoDB:

| # | Widget                  | Concepto Redis                                   |
|---|-------------------------|--------------------------------------------------|
| 1 | Caché de consultas      | `GET` / `SET … EX 60` delante de MongoDB (cache-aside) |
| 2 | Turnos en tiempo real   | `PUBLISH` / `SUBSCRIBE chat:sala1` + `SET lock NX EX 30` |
| 3 | Mapa sincronizado       | `PUBLISH` / `SUBSCRIBE mapa:sala1` con Leaflet   |

Al entrar se elige un rol:

- **Publicador** (solo uno a la vez): llama fichas de atención y mueve el mapa.
- **Suscriptor** (varios): recibe las fichas y ve el mapa moverse en tiempo real.

Debajo de cada widget hay un terminal que imita `redis-cli` con los comandos
que realmente se ejecutaron.

## Estructura

```
app.py            Flask: sirve la página y expone la API JSON
conexiones.py     Clientes de MongoDB y Redis (lee el .env)
cache.py          Widget 1: obtener_asignatura() con cache-aside, TTL 60 s
pubsub.py         Widgets 2 y 3: lock del publicador, PUBLISH y SUBSCRIBE (SSE)
templates/index.html
static/estilo.css
static/app.js     Lógica de la interfaz: rol, caché, turnos, mapa
Dockerfile · docker-compose.yml · requirements.txt · .env
```

## Puesta en marcha

Requiere que MongoDB y Redis ya estén corriendo en Docker (proyectos
`bd-mongo` y `bd-redis-docker`). La app se une a sus redes.

1. Revisar `.env` (`MONGO_URI`, `REDIS_URL`, redes Docker y `APP_PORT`).
2. Construir y levantar:

```bash
docker compose up --build
```

3. Abrir <http://localhost:8077>. Para la demo, abrir una pestaña como
   **publicador** y una o más como **suscriptor**.

Para correr sin Docker, cambiar los hosts del `.env` a `localhost` y:

```bash
pip install -r requirements.txt
python app.py
```

## Cómo funciona cada widget

### 1 · Caché (cache.py)

```python
cache = redis.get(f"asignatura:{codigo}")        # 1. ¿está en Redis?   -> HIT (CACHE)
if not cache:
    doc = mongo.asignatura.find_one({...})       # 2. MISS: ir a MongoDB (BD)
    redis.set(clave, json.dumps(doc), ex=60)     # 3. guardar 60 segundos
```

El botón **Consultar** mide el tiempo total y muestra el origen (`BD` o
`CACHE`), el TTL restante y un historial de barras para comparar. **DEL**
borra la clave y fuerza el siguiente MISS.

### 2 · Turnos (pubsub.py)

- Al elegir *publicador* el navegador ejecuta `SET lock:publicador <token> NX EX 30`.
  Si la clave ya existe, Redis devuelve `nil` y el rol queda bloqueado.
  El publicador renueva el lock cada 10 s (`EXPIRE`) y lo libera al salir;
  si la pestaña muere, expira sola a los 30 s.
- Cada ficha se envía con `PUBLISH chat:sala1 "Ficha A-12"`. Redis responde
  con el número de suscriptores que la recibieron.
- El servidor hace `SUBSCRIBE chat:sala1 mapa:sala1` por cada suscriptor y
  reenvía los mensajes al navegador con *Server-Sent Events* (`EventSource`).

### 3 · Mapa

Mismo mecanismo: cuando el publicador suelta el marcador (`dragend`) o termina
de mover/hacer zoom en el mapa (`moveend`), hace
`PUBLISH mapa:sala1 {"lat", "lng", "zoom", "marcador": {"lat", "lng"}}` y los
suscriptores ejecutan `map.setView(...)` y `marker.setLatLng(...)` al recibirlo.

## Comandos Redis empleados

| Comando                                 | Uso                                         |
|-----------------------------------------|---------------------------------------------|
| `GET clave` / `SET clave valor EX 60`   | Leer / guardar en caché con expiración      |
| `TTL clave` / `DEL clave`               | Segundos restantes / invalidar caché        |
| `SET lock:publicador token NX EX 30`    | Lock: solo escribe si **no existe**         |
| `EXPIRE lock:publicador 30`             | Renovar el lock                             |
| `PUBLISH canal mensaje`                 | Emitir; devuelve cuántos oyentes lo recibieron |
| `SUBSCRIBE canal …`                     | Escuchar canales                            |
