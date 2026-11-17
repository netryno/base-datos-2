"""Servidor web (Flask): sirve la interfaz, expone la API JSON y el canal SSE del juego."""
import logging
from functools import wraps

from flask import Flask, Response, jsonify, render_template, request, stream_with_context
from pymongo.errors import PyMongoError
from redis.exceptions import RedisError

import catalogo
import config
import conexiones
import juego
import pubsub
import semilla

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = Flask(__name__)


# ---------------------------------------------------------- utilidades ----

def datos() -> dict:
    return request.get_json(silent=True) or {}


def session_id() -> str:
    """El navegador se identifica con la cabecera X-Session-Id (o session_id en el cuerpo / query)."""
    return request.headers.get("X-Session-Id") or datos().get("session_id") or request.args.get("session_id") or ""


def solo_profesor(fn):
    @wraps(fn)
    def envoltura(*args, **kwargs):
        if not pubsub.es_profesor(session_id()):
            return jsonify({"error": "Solo el Profesor activo puede hacer esto.", "lost_lock": True}), 403
        return fn(*args, **kwargs)
    return envoltura


@app.errorhandler(juego.ErrorJuego)
def error_juego(e: juego.ErrorJuego):
    return jsonify({"error": str(e), **e.extra}), e.codigo


@app.errorhandler(catalogo.ErrorCatalogo)
def error_catalogo(e: catalogo.ErrorCatalogo):
    return jsonify({"error": str(e)}), e.codigo


@app.errorhandler(RedisError)
def error_redis(e):
    app.logger.error("Redis no disponible: %s", e)
    return jsonify({"error": "Redis no disponible: servicio degradado, comando rechazado.", "degraded": True}), 503


@app.errorhandler(PyMongoError)
def error_mongo(e):
    app.logger.error("MongoDB no disponible: %s", e)
    return jsonify({"error": "MongoDB no disponible.", "degraded": True}), 503


# --------------------------------------------------------------- vistas ----

@app.get("/")
def inicio():
    return render_template("index.html")


@app.get("/api/config")
def configuracion():
    return jsonify(config.publica())


@app.get("/api/health")
def salud():
    estado = conexiones.salud()
    codigo = 200 if all(v == "ok" for v in estado.values()) else 503
    return jsonify(estado), codigo


# ------------------------------------------------- sesión del Profesor ----

@app.get("/api/session/publisher")
def estado_publicador():
    return jsonify(pubsub.estado_lock())


@app.post("/api/session/claim-publisher")
def reclamar_publicador():
    d = datos()
    nombre = " ".join((d.get("name") or "").split())
    if not config.MIN_NAME_LENGTH <= len(nombre) <= config.MAX_NAME_LENGTH:
        return jsonify({"error": f"El nombre debe tener entre {config.MIN_NAME_LENGTH} y {config.MAX_NAME_LENGTH} caracteres."}), 400
    sid = session_id()
    if not sid:
        return jsonify({"error": "Falta el identificador de sesión."}), 400
    r = pubsub.reclamar_lock(sid, nombre)
    if not r["ok"]:
        return jsonify({"error": f"Ya hay un Profesor activo ({r['lock'].get('name', '?')}). Entra como Jugador.",
                        "ttl": r["ttl"], "comandos": [(r["comando"], r["respuesta"])]}), 409
    return jsonify({"ok": True, "ttl": r["ttl"], "lock": r["lock"], "comandos": [(r["comando"], r["respuesta"])]})


@app.post("/api/session/heartbeat")
def latido():
    ttl = pubsub.renovar_lock(session_id())
    return jsonify({"ttl": ttl, "ok": ttl > 0,
                    "comandos": [(f"EXPIRE {pubsub.LOCK} {config.PUBLISHER_LOCK_TTL}", f"(integer) {1 if ttl > 0 else 0}")]})


@app.post("/api/session/release-publisher")
def liberar_publicador():
    ok = pubsub.liberar_lock(session_id())
    return jsonify({"ok": ok, "comandos": [(f"DEL {pubsub.LOCK}", f"(integer) {1 if ok else 0}")]})


# ---------------------------------------------- categorías y preguntas ----

@app.get("/api/categories")
def listar_categorias():
    return jsonify(catalogo.listar_categorias())


@app.post("/api/categories")
@solo_profesor
def crear_categoria():
    return jsonify(catalogo.crear_categoria(datos().get("name", ""))), 201


@app.delete("/api/categories/<cid>")
@solo_profesor
def eliminar_categoria(cid):
    return jsonify(catalogo.eliminar_categoria(cid))


@app.get("/api/questions")
@solo_profesor
def listar_preguntas():
    return jsonify(catalogo.listar_preguntas(request.args.get("category_id")))


@app.post("/api/questions")
@solo_profesor
def crear_pregunta():
    d = datos()
    return jsonify(catalogo.crear_pregunta(
        d.get("category_id", ""),
        d.get("text", ""),
        d.get("options", {}),
        d.get("correct", ""),
        d.get("duration_seconds"),
        d.get("code_block"),
    )), 201


@app.delete("/api/questions/<qid>")
@solo_profesor
def eliminar_pregunta(qid):
    return jsonify(catalogo.eliminar_pregunta(qid))


# -------------------------------------------------------------- partidas ----

@app.get("/api/games/current")
def partida_actual():
    gid = juego.partida_actual_id()
    if not gid or not juego.cargar_estado(gid):
        return jsonify({"game": None})
    return jsonify({"game": juego.instantanea(gid, session_id())})


@app.post("/api/games/reset")
@solo_profesor
def reiniciar_sesion_juego():
    return jsonify(juego.reiniciar_sesion())


@app.post("/api/games")
@solo_profesor
def crear_partida():
    d = datos()
    return jsonify(
        juego.crear_partida(
            d.get("category_id", ""),
            d.get("question_ids"),
            d.get("question_count"),
        )
    ), 201


@app.post("/api/games/<gid>/start")
@solo_profesor
def iniciar_partida(gid):
    return jsonify(juego.iniciar(gid))


@app.post("/api/games/<gid>/next")
@solo_profesor
def siguiente_pregunta(gid):
    return jsonify(juego.siguiente(gid))


@app.post("/api/games/<gid>/cancel")
@solo_profesor
def cancelar_partida(gid):
    return jsonify(juego.cancelar(gid))


@app.post("/api/games/<gid>/join")
def unirse(gid):
    return jsonify(juego.unirse(gid, session_id(), datos().get("name", "")))


@app.post("/api/games/<gid>/leave")
def salir(gid):
    return jsonify(juego.salir(gid, session_id()))


@app.post("/api/games/<gid>/clear-lobby")
@solo_profesor
def vaciar_sala(gid):
    return jsonify(juego.vaciar_sala(gid))


@app.post("/api/games/<gid>/answer")
def responder(gid):
    d = datos()
    try:
        idx = int(d.get("idx"))
    except (TypeError, ValueError):
        return jsonify({"error": "Índice de pregunta inválido."}), 400
    confirmar = d.get("confirm") is True
    return jsonify(juego.responder(gid, session_id(), idx, d.get("option"), confirmar))


@app.get("/api/games/<gid>/state")
def estado_partida(gid):
    return jsonify(juego.instantanea(gid, session_id()))


# ---------------------------------------------------------- SSE (Pub/Sub) ----

@app.get("/api/events")
def eventos():
    """Redis SUBSCRIBE -> SSE. Siempre escucha games:events; si hay game_id, también game:{id}:events
    y envía primero un state_snapshot para conectar/reconectar."""
    gid = request.args.get("game_id") or ""
    rol = request.args.get("role", "jugador")
    sid = session_id()
    canales = [pubsub.CANAL_GLOBAL]
    inicial = []
    if gid and juego.cargar_estado(gid):
        canales.append(pubsub.canal_partida(gid))
        inicial.append(pubsub.sse("state_snapshot", juego.instantanea(gid, sid)))
    headers = {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(
        stream_with_context(pubsub.escuchar(canales, rol, inicial)),
        mimetype="text/event-stream",
        headers=headers,
    )


# ------------------------------------------------------------- arranque ----

def preparar() -> None:
    try:
        catalogo.preparar_indices()
        semilla.precargar()                      # preguntas.json -> MongoDB (solo lo que falte)
    except PyMongoError as e:
        app.logger.warning("MongoDB no disponible al arrancar (índices/precarga): %s", e)
    except (ValueError, OSError) as e:
        app.logger.error("Fichero de precarga inválido: %s", e)
    juego.recuperar_temporizadores()


preparar()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.APP_PORT, threaded=True)
