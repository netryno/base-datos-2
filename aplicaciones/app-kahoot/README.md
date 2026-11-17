# Quiz en tiempo real · Redis Pub/Sub + MongoDB

Web app tipo *Kahoot* para la materia Base de Datos II. Un **Profesor / Publicador**
registra preguntas por categoría y lanza partidas; varios **Jugadores / Suscriptores**
responden cada pregunta en 10 segundos y ven el ranking Top 10 al instante. Al final
se muestra el podio (1.°, 2.°, 3.°) y el resultado se guarda en MongoDB.

### Respuesta del jugador («¿seguro?»)

Al tocar una opción queda la selección **pendiente**: el alumno ve **¿Estás seguro?** con **Sí** y **No**.
- **Sí**: confirma la respuesta; con `ANSWER_POLICY=first` ya no puede cambiarla.
- **No**: borra la selección y puede elegir otra opción mientras haya tiempo.
- Si el tiempo termina con una opción elegida pero **sin pulsar Sí**, esa selección **cuenta igual** (el servidor la guarda como pendiente y al cerrar la pregunta la evalúa).
- Si **todos los jugadores inscritos** ya **confirmaron** su respuesta (`confirm: true`) **antes** de que acabe `QUESTION_DURATION`, el servidor cierra la pregunta de inmediato. Quien solo eligió opción sin confirmar no cuenta para ese cierre; al vencer el tiempo, su selección pendiente sí se evalúa.

| Concepto                          | Dónde vive                                                        |
|-----------------------------------|-------------------------------------------------------------------|
| Un solo Profesor                  | `SET publisher:lock <json> NX EX 15` + latido `EXPIRE` cada 5 s   |
| Estado en vivo de la partida      | `game:current`, `game:{id}:state` (JSON, TTL), `game:{id}:players`, `game:{id}:answers:{idx}` (HASH) |
| Tiempo real                       | `PUBLISH / SUBSCRIBE game:{id}:events` → backend → navegador (SSE) |
| Banco de preguntas e histórico    | MongoDB: `categories`, `questions`, `games`                       |

El navegador **nunca** habla con Redis ni Mongo: usa `fetch` para los comandos y
`EventSource` (SSE) para recibir los eventos que el backend reenvía desde Redis.
El servidor es la única fuente de verdad del temporizador y del puntaje.

## Estructura

```
app.py                 Flask: página, API JSON y canal SSE
config.py              Variables de entorno (duración, top N, TTLs, bonus…)
conexiones.py          Clientes de MongoDB y Redis (lee el .env)
pubsub.py              Lock del Profesor, PUBLISH y SUBSCRIBE → SSE
catalogo.py            Categorías y preguntas en MongoDB
juego.py               Motor de la partida: estados, temporizador, puntaje, ranking, histórico
templates/index.html   Ingreso (nombre + rol), panel del Profesor, pantalla del Jugador
static/app.js          Lógica de la interfaz (sin frameworks)
static/estilo.css
Dockerfile · docker-compose.yml · requirements.txt · .env
preguntas.json         Banco inicial (9 categorías × 14 preguntas); precarga idempotente al arrancar
```

### Precarga `preguntas.json`

Al iniciar el backend se llama a `semilla.precargar()`: lee `preguntas.json` (ruta configurable con `SEED_FILE`) e inserta en MongoDB solo **categorías y preguntas que aún no existan** (misma categoría por nombre, misma pregunta por texto). Si ya tenías datos de una versión anterior, no se duplican.

Categorías del fichero: **Redis**, **Mongo**, **ChromaDB**, **SQL Server**, **MySQL**, **PostgreSQL**, **Base de datos** (14 preguntas cada una).

## Puesta en marcha

Requiere que MongoDB y Redis ya estén corriendo en Docker (proyectos `bd-mongo` y
`bd-redis-docker`, contenedores `mongo-d` y `redis-d`). La app se une a sus redes.

1. Revisar `.env` (`MONGO_URI`, `REDIS_URL`, redes Docker y `APP_PORT`).
2. Construir y levantar:

```bash
docker compose up --build
```

3. Abrir <http://localhost:8078>. Para la demo: una pestaña como **Profesor** y varias
como **Jugador** (cada pestaña es un participante distinto).

Sin Docker: cambiar los hosts del `.env` a `localhost` y

```bash
pip install -r requirements.txt
python app.py
```

## Exponer el juego por túnel (Cloudflare, ngrok, localtunnel…)

**Sí puede funcionar** el tiempo real si el túnel reenvía **HTTP estándar** y no corta las conexiones largas:

- Las peticiones de la API van por `fetch` (POST/GET) como cualquier página.
- Los eventos en vivo usan **Server-Sent Events** (`EventSource`) en `/api/events`: es una respuesta HTTP que se mantiene abierta y va enviando datos.

**Requisitos prácticos:**

1. El túnel debe apuntar al **mismo puerto** que sirve la app (`APP_PORT`, por defecto 8078).
2. Usa **HTTPS** en la URL pública del túnel (recomendado); los navegadores lo prefieren para APIs modernas.
3. Si tras abrir por túnel no llegan eventos (partida “muerta” en tiempo real), suele ser **buffering del proxy** sobre `/api/events` (SSE). Los **quick tunnels** de Cloudflare (`trycloudflare.com`) suelen bufferizar el cuerpo de SSE aunque la cabecera sea `200 text/event-stream`; por eso el chip de conexión pasa a **«sondeo HTTP»** y la UI consulta `/api/games/.../state` cada ~2 s. Para forzar solo sondeo: `STATE_POLL_INTERVAL=2` en `.env`. También ayuda `SSE_PING_INTERVAL=3` y reiniciar el contenedor. Túneles con WebSockets (ngrok, Cloudflare Tunnel nombrado) suelen llevar SSE bien.
4. **MongoDB y Redis** siguen siendo locales o en tu red: el túnel solo expone el **Flask**. No necesitas exponer los puertos 27017/6379 a Internet para que los alumnos jueguen.

## Variables de entorno (`.env`)

| Variable                | Defecto | Uso                                                        |
|-------------------------|---------|------------------------------------------------------------|
| `APP_PORT`              | 8078    | Puerto (host y contenedor)                                 |
| `MONGO_URI` / `DB_NAME` |         | Conexión a MongoDB (`bd-kahoot`)                           |
| `REDIS_URL`             |         | Conexión a Redis                                           |
| `QUESTION_DURATION`     | 10      | Segundos por pregunta                                      |
| `TOP_N`                 | 10      | Tamaño del ranking                                         |
| `BASE_POINTS`           | 10      | Puntos por acierto                                         |
| `SPEED_BONUS_ENABLED`   | true    | Bonus por velocidad: hasta `SPEED_BONUS_MAX` × restante/duración |
| `SPEED_BONUS_MAX`       | 5       |                                                            |
| `ANSWER_POLICY`         | first   | `first` (HSETNX) o `last` (HSET) si un jugador envía varias |
| `AUTO_ADVANCE_SECONDS`  | 0       | 0 = el Profesor pulsa "Siguiente"; >0 avanza solo           |
| `PUBLISHER_LOCK_TTL`    | 15      | TTL del lock del Profesor                                  |
| `HEARTBEAT_INTERVAL`    | 5       | Cada cuánto renueva el lock el navegador                   |
| `SSE_PING_INTERVAL`     | 5       | Comentario SSE cada N s en `/api/events` (túneles/proxy)   |
| `STATE_POLL_INTERVAL`   | 0       | Sondeo HTTP cada N s; 0 = auto si SSE no responde en ~3.5 s |
| `MIN_NAME_LENGTH` / `MAX_NAME_LENGTH` | 2 / 20 | Longitud del nombre                           |
| `GAME_STATE_TTL`        | 3600    | Segundos extra que vive el estado en Redis                 |

## Flujo de una partida

```
LOBBY ─(Profesor lanza)→ QUESTION_STARTED ─(timeout)→ QUESTION_CLOSED → RANKING_SHOWN
                                ▲                                              │
                                └──────────── (Profesor: Siguiente) ───────────┤
                                                                   (última) → GAME_OVER
```

1. El Profesor entra con su nombre: `SET publisher:lock NX EX 15`. Si otra pestaña ya lo
   tiene, Redis responde `nil` y solo puede entrar como Jugador. El lock se renueva cada
   5 s; si la pestaña se cierra, expira solo y otro puede reclamarlo.
2. Crea categorías y preguntas (a/b/c/d, una correcta) → MongoDB.
3. Crea la partida (título + categoría, opcionalmente un subconjunto de preguntas; orden
   aleatorio). Se publica `game_created` y los Jugadores entran al **lobby**, donde todos
   ven el widget de participantes con un avatar (silueta) aleatorio.
4. Al lanzar, cada pregunta publica `question_started` con el `deadline` del servidor; el
   cliente solo dibuja la cuenta regresiva. Cada respuesta se guarda con
   `HSETNX game:{id}:answers:{idx} <player> {option, ts}` (atómico: solo cuenta la primera).
5. Al vencer el tiempo el servidor cierra la pregunta, calcula puntos (10 + bonus por
   velocidad), publica `question_closed` (correcta + votos por opción) y `ranking_shown`
   (Top 10). Desempate: puntaje → menor tiempo acumulado → orden de ingreso.
6. El Profesor pulsa **Siguiente**; tras la última pregunta se publica `game_over` con el
   podio y el ranking, y la partida se guarda en `games` (MongoDB).

Casos cubiertos: nombre duplicado rechazado; quien entra con la partida en curso es
**espectador** hasta la próxima; recarga de página recupera el estado desde
`game:{id}:state` (`state_snapshot` al reconectar); categoría sin preguntas no se puede
lanzar; cancelación en cualquier estado (`game_cancelled`); Redis caído → 503 "servicio
degradado"; si el backend se reinicia con una pregunta abierta, reprograma su cierre.

## API

| Método y ruta                             | Quién     | Descripción                                   |
|-------------------------------------------|-----------|-----------------------------------------------|
| `POST /api/session/claim-publisher`       | todos     | Toma el lock (409 si está ocupado)            |
| `POST /api/session/heartbeat`             | Profesor  | Renueva el lock                               |
| `POST /api/session/release-publisher`     | Profesor  | Libera el lock                                |
| `GET/POST /api/categories` · `DELETE /api/categories/{id}` | GET todos / resto Profesor |         |
| `GET/POST /api/questions` · `DELETE /api/questions/{id}`   | Profesor  |                                  |
| `POST /api/games`                         | Profesor  | Crea la partida en LOBBY                      |
| `POST /api/games/reset`                   | Profesor  | Borra la partida en Redis y emite `session_reset` (jugadores vuelven al ingreso) |
| `POST /api/games/{id}/start|next|cancel`  | Profesor  | Controla el avance                            |
| `POST /api/games/{id}/clear-lobby`        | Profesor  | Vacía el lobby (quita a todos; vuelven a unirse) |
| `POST /api/games/{id}/join|leave|answer`  | Jugador   | Entrar, salir del lobby, responder            |
| `GET /api/games/current` · `GET /api/games/{id}/state` | todos | Estado para (re)conectar              |
| `GET /api/events?game_id=&session_id=&role=` | todos  | SSE: `state_snapshot` + eventos de Redis      |
| `GET /api/health` · `GET /api/config`     | todos     | Salud de Redis/Mongo · configuración pública  |

La sesión se identifica con la cabecera `X-Session-Id` (un UUID por pestaña).

Eventos Pub/Sub (`{ type, game_id, ts, payload }`): `session_reset` (Profesor reinicia sesión; canónico global), `game_created`, `player_joined`,
`player_left`, `lobby_cleared` (lobby vaciado por el Profesor), `game_started`, `question_started`, `answer_received` (solo Profesor),
`question_closed`, `ranking_shown`, `game_over`, `game_cancelled`.
