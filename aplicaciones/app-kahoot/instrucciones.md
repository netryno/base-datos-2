Sobre esta base de proyecto, 
- practicamente rescatar conexion a bd mongo y redis
- rescatar el docker compose y sus tecnologia en python
- 

Requiero una web app, para lo siguiente.

- Un apartado para registrar , preguntas con su opciones: a, b, c, d. (que seria respuestas y solo una puede ser respuesta)
- Al ingresar al apartado, solo una puede ingresar como adminstrador y puedas gestionar estas preguntas. (que seria el publicador en redis)
- El publicador solo puede ser 1, el primero que tome , se ocuparia, los demas ya no pudieran.
- Los demas que ingresan, serian los suscriptores, ademas a ellos les saldra una patalla donde podra particpara del juego
- el juego cnsiste el que el publicador publica una pregunta con sus opcinoes y los suscriptores tiene 10 segundos para responder o escoger una opcion.
- cuando termine 10 segundos, se mostra en ranking de los top  10. y pasarian a segunada pregunta y con la misma dinaamica.
- y cuando termina los 5 pregutnas o las que tenga la categoria , finalizaria y se veria el podio 1ro 2do y 4ro, y los otro 7 en lista.
- los suscritpres podran su nombre obligatoriamente al ingresar.
- el profesor podra su nombre , pero solo uno pude ser profesor.
- provechar el tiempo real de redis (pub/sus), par amostrar preguntas, para mostrar teporizador y detalles.
- el profesor puede rgistrar preguntas por catagoria, y al lanzar una juego , pueda poner un titulo y posibildad de escoger con que categoria jugar
- 



Especificación — Web App de Quiz en Tiempo Real (Redis Pub/Sub + MongoDB)
1. Objetivo y alcance
Construir una web app tipo quiz (estilo Kahoot) donde un Profesor/Publicador registra preguntas por categoría y lanza partidas, y varios Jugadores/Suscriptores participan en tiempo real respondiendo preguntas con temporizador de 10 segundos. El estado se propaga vía Redis Pub/Sub y los resultados finales se persisten en MongoDB. Se reutiliza el docker-compose base (Mongo + Redis + backend Python).

Fuera de alcance (explícito): cuentas de usuario reales/autenticación con contraseña, múltiples partidas simultáneas, historial avanzado, aplicación móvil nativa.

2. Roles y permisos
Rol	Cantidad	Puede hacer
Profesor / Publicador	1 por instancia (lock en Redis)	Registra preguntas y categorías, crea y lanza partidas, controla el avance
Jugador / Suscriptor	N (sin límite definido)	Se une a una partida en lobby, responde preguntas, ve rankings
Los roles son mutuamente excluyentes en una misma sesión de navegador.

El Profesor es el Publicador: es la misma entidad, no dos roles separados.

El primer usuario que reclama el rol de Profesor obtiene el lock; los demás solo pueden entrar como Jugadores mientras el lock esté activo.

El lock de Profesor se mantiene con heartbeat y expira por TTL, pero se renueva mientras esta en navegador.

El nombre es obligatorio para ambos roles al ingresar (sin login/contraseña; identificador de sesión).

3. Reglas de negocio
3.1 Preguntas
Cada pregunta tiene: texto, opciones (a, b, c, d), una sola opción correcta, y pertenece a una categoría.

El Profesor registra preguntas y categorías desde su panel.

Las categorías las administra el Profesor (crear/listar); no se autogeneran.

3.2 Partida
Al lanzar una partida el Profesor define: título y categoría.

Se juegan las preguntas de la categoría seleccionada (todas, o el subconjunto que el Profesor elija; por defecto todas).

Orden de preguntas: aleatorio dentro de la categoría.

Solo existe una partida activa a la vez (consistente con "un solo publicador").

Para cada pregunta nueva el profesor preciona un boton y los suscriptores tien 10 segundos para responder. y luego se repite el ciclo por otra preguta
el profesor debe precionar siguiente.

3.3 Preguntas y temporizador
Cada pregunta dura 10 segundos, configurables por variable de entorno.

El servidor es la única fuente de verdad del tiempo. El cliente solo renderiza la cuenta regresiva a partir del deadline recibido.

Una respuesta por jugador por pregunta; se toma la última enviada antes del deadline (o la primera, según se fije en configuración — por defecto: la primera).

Al terminar el tiempo, la pregunta se cierra y se calcula el ranking en el servidor.

3.4 Puntaje y ranking
Respuesta correcta: 10 puntos base.

Bonus por velocidad opcional (configurable, activado por defecto): hasta +5 proporcional al tiempo restante (5 * restante / duración).

Respuesta incorrecta o sin respuesta: 0 puntos.

Desempate: mayor puntaje → menor tiempo total acumulado → orden de ingreso.

Ranking tras cada pregunta: Top 10 (si hay menos jugadores, se muestran los que haya).

Podio final: 1.°, 2.°, 3.° + lista de los siguientes hasta completar 10.

3.5 Jugadores
Nombre obligatorio, no vacío, longitud acotada (configurable, por defecto 2–20 caracteres).

Nombres duplicados dentro de una partida: no permitidos (se rechaza el ingreso con un nombre ya tomado en la sala).

Un jugador que ingresa después de iniciada la partida entra como espectador hasta la siguiente (decisión: no se une a la partida en curso).

Reconexión: si un jugador recarga la página, recupera su estado desde Redis (puntaje, pregunta actual, si ya respondió). Las preguntas que se cerraron mientras estuvo desconectado cuentan como no respondidas (0 puntos).


4. Flujo de una partida (estados)
text
LOBBY
  └─(profesor lanza)→ QUESTION_STARTED (por cada pregunta)
                        └─(timeout 10s)→ QUESTION_CLOSED
                                            └─→ RANKING_SHOWN (top 10)
                                                  └─(siguiente)→ QUESTION_STARTED
                                                  └─(última)→ GAME_OVER (podio + top 10)
LOBBY: se muestran jugadores conectados; el Profesor puede lanzar.

El Profesor puede cancelar la partida en cualquier estado → GAME_OVER (sin podio).

No hay partidas simultáneas.

Cada transición publica un evento en Redis y persiste el estado de la partida en Redis (con TTL).

5. Modelo de datos
MongoDB (persistencia)
categories: { _id, name }

questions: { _id, category_id, text, options: {a,b,c,d}, correct: "a"|"b"|"c"|"d", created_at }

games: { _id, title, category_id, started_at, ended_at, question_ids[], ranking_final[] } — se escribe al finalizar para histórico.

Redis (estado en vivo + pub/sub)
publisher:lock → {session_id, name, acquired_at} — TTL 15 s, heartbeat cada 5 s.

game:current → game_id de la partida activa (o ausente si no hay).

game:{game_id}:state → JSON con estado completo (estado, pregunta actual, deadline, jugadores, puntajes, respuestas). TTL = duración máxima + 1 h.

game:{game_id}:players → hash player_id → {name, score, total_time}.

game:{game_id}:answers:{question_idx} → hash player_id → {option, ts}.

Canal pub/sub: game:{game_id}:events (único por partida).

6. Contrato de eventos Pub/Sub
Todos los mensajes son JSON con { type, game_id, ts, payload }.

Evento	Emisor	Consumidor	Payload
player_joined	Backend (al unirse)	Todos	{ player_id, name }
player_left	Backend	Todos	{ player_id }
game_started	Profesor→Backend	Todos	{ title, category, total_questions }
question_started	Backend	Todos	{ idx, text, options, deadline, duration }
answer_received	Backend	Profesor (conteo)	{ idx, count }
question_closed	Backend	Todos	{ idx, correct }
ranking_shown	Backend	Todos	{ idx, top10[] }
game_over	Backend	Todos	{ podium[], ranking[] }
game_cancelled	Profesor→Backend	Todos	{}
Nota: el navegador nunca habla directo con Redis. El flujo es: Redis Pub/Sub → backend Python (suscriptor) → WebSocket/SSE → navegador, y a la inversa para comandos del Profesor/Jugador.

7. API HTTP (mínimo)
POST /api/session/claim-publisher → intenta tomar el lock; 409 si ya está ocupado.

POST /api/session/heartbeat → renueva lock del Profesor.

POST /api/session/release-publisher → libera lock.

GET /api/categories · POST /api/categories (solo Profesor).

GET /api/questions?category_id= · POST /api/questions (solo Profesor).

POST /api/games (solo Profesor) → crea partida en LOBBY, devuelve game_id.

POST /api/games/{id}/start (solo Profesor).

POST /api/games/{id}/cancel (solo Profesor).

POST /api/games/{id}/join → { name } del Jugador; valida duplicados.

GET /api/games/{id}/state → estado actual (para reconexión).

8. WebSocket / SSE
Endpoint único: WS /ws/game/{game_id}?session_id=...&role=...

Cliente → Servidor:

submit_answer { idx, option } (Jugador)

next_question {} (Profesor, opcional si el avance es automático; por defecto automático al cerrar ranking durante 5 s)

Servidor → Cliente: replica de los eventos de §6 más state_snapshot al conectar/reconectar.

9. Reglas duras (no negociables)
Un solo Profesor/Publicador por instancia, garantizado por publisher:lock en Redis con TTL 15 s y heartbeat cada 5 s. Si expira, otro puede reclamarlo, siempre y cuando no cierre su pantalla.

El servidor es la única fuente de verdad del temporizador y del puntaje.

Toda transición se publica en game:{game_id}:events y se persiste en game:{game_id}:state.

El ranking se calcula en el servidor; el cliente nunca calcula puntajes.

La reconexión se resuelve leyendo game:{game_id}:state (no de pub/sub, que no persiste).

Top 10 siempre que haya suficientes jugadores; podio = 1.°, 2.°, 3.°.

Nombres únicos por partida, no vacíos, longitud acotada.

Toda configuración (duración de pregunta, top N, TTLs, bonus) va por variables de entorno.

10. Infraestructura (docker-compose)
Servicios: mongo, redis, backend (Python).

Backend: FastAPI + WebSockets (recomendado) o SSE. Cliente Redis (redis-py) y Mongo (motor/pymongo).

Dependencias: el backend usa depends_on + healthcheck de Mongo y Redis antes de arrancar.

Variables de entorno clave: MONGO_URI, REDIS_URL, QUESTION_DURATION=10, TOP_N=10, PUBLISHER_LOCK_TTL=15, HEARTBEAT_INTERVAL=5, SPEED_BONUS_ENABLED=true, MAX_NAME_LENGTH=20.

Volúmenes persistentes para Mongo.

Front: servido por el backend (estático) o servicio nginx aparte (a definir en implementación).

11. Casos borde a cubrir
Profesor cierra pestaña → lock expira por TTL y otro puede reclamarlo.

Jugador recarga en mitad de pregunta → recibe state_snapshot y puede responder si aún hay tiempo.

Jugador entra tras el inicio → espectador hasta la próxima partida.

Menos de 10 jugadores → ranking muestra los disponibles; podio solo con los existentes.

Empate → desempate por tiempo acumulado y orden de ingreso.

Nombre duplicado → rechazo con error claro.

Sin preguntas en la categoría → no se permite lanzar la partida.

Redis caído → el backend informa estado degradado y rechaza comandos (no se pierde consistencia por cálculo en cliente).

Partida cancelada → todos reciben game_cancelled y vuelven a LOBBY/vista inicial.

12. Criterios de aceptación (resumen)
□ Un solo Profesor a la vez; lock verificable y recuperable.
□ Profesor crea categorías, preguntas (a/b/c/d, una correcta) y lanza partida con título + categoría.
□ Jugadores se unen con nombre único y ven la pregunta en ≤ 1 s tras el inicio.
□ Temporizador de 10 s coherente entre todos los clientes (fuente: servidor).
□ Al cerrar cada pregunta se emite ranking Top 10.
□ Al finalizar se muestra podio (1.°, 2.°, 3.°) + lista hasta 10.
□ Reconexión de jugador recupera estado correcto.
□ Resultado final persistido en Mongo.
□ Todo el stack levanta con docker compose up y funciona sin configuración manual extra.
□ Mientras se suscriban antes de que inicie la partida, debe verse los susscriptores en un wdiget tanto para todos ( alumnos y profesor)
Una silueta al azar para cada alumno (abatar)