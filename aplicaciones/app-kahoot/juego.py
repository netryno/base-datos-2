"""
Motor de la partida. El servidor es la única fuente de verdad del tiempo y del puntaje.

Redis (estado en vivo)
  game:current                     -> game_id de la partida activa
  game:{id}:state                  -> JSON con el estado completo (TTL)
  game:{id}:players                -> HASH player_id -> {name, avatar, score, total_time, order}
  game:{id}:answers:{idx}          -> HASH player_id -> {option, ts}
  game:{id}:events                 -> canal Pub/Sub de la partida

MongoDB (histórico)
  games: { _id, title, category_id, started_at, ended_at, question_ids[], ranking_final[] }

Estados: LOBBY -> QUESTION_STARTED -> QUESTION_CLOSED -> RANKING_SHOWN -> (QUESTION_STARTED | GAME_OVER)
"""
import json
import logging
import random
import threading
from datetime import datetime, timezone

from bson import ObjectId

import catalogo
import config
import pubsub
from conexiones import mongo, redis
from pubsub import ahora_ms, canal_partida, publicar

log = logging.getLogger("juego")

K_CURRENT = "game:current"
LOBBY, STARTED, CLOSED, RANKING, OVER = "LOBBY", "QUESTION_STARTED", "QUESTION_CLOSED", "RANKING_SHOWN", "GAME_OVER"

AVATAR_FORMAS = 8
AVATAR_COLORES = 10

_temporizadores: dict[str, threading.Timer] = {}


class ErrorJuego(Exception):
    def __init__(self, mensaje: str, codigo: int = 400, **extra):
        super().__init__(mensaje)
        self.codigo = codigo
        self.extra = extra


# ---------------------------------------------------------------- Claves ----

def k_state(gid: str) -> str:
    return f"game:{gid}:state"


def k_players(gid: str) -> str:
    return f"game:{gid}:players"


def k_answers(gid: str, idx: int) -> str:
    return f"game:{gid}:answers:{idx}"


def _duracion_pregunta(q: dict) -> int:
    d = q.get("duration_seconds")
    if d is not None:
        try:
            v = int(d)
            if 5 <= v <= 300:
                return v
        except (TypeError, ValueError):
            pass
    return config.QUESTION_DURATION


def _ttl_estado(estado: dict) -> int:
    """TTL = duración máxima de la partida + GAME_STATE_TTL."""
    max_d = max((_duracion_pregunta(q) for q in estado.get("questions") or []), default=config.QUESTION_DURATION)
    return estado["total_questions"] * (max_d + 60) + config.GAME_STATE_TTL


# ---------------------------------------------------------- Estado Redis ----

def partida_actual_id() -> str | None:
    return redis.get(K_CURRENT)


def cargar_estado(gid: str) -> dict | None:
    crudo = redis.get(k_state(gid))
    return json.loads(crudo) if crudo else None


def _exigir_estado(gid: str) -> dict:
    estado = cargar_estado(gid)
    if not estado:
        raise ErrorJuego("La partida no existe o ya expiró.", 404)
    return estado


def guardar_estado(estado: dict) -> None:
    redis.set(k_state(estado["game_id"]), json.dumps(estado, ensure_ascii=False), ex=_ttl_estado(estado))


def _jugadores(gid: str) -> dict[str, dict]:
    return {pid: json.loads(v) for pid, v in redis.hgetall(k_players(gid)).items()}


def _jugadores_para_evento(gid: str) -> list[dict]:
    """Lista ordenada para payload de eventos y vistas (misma forma que instantanea.players)."""
    jugadores = _jugadores(gid)
    return [{"player_id": j["player_id"], "name": j["name"], "avatar": j["avatar"], "order": j["order"]}
            for j in sorted(jugadores.values(), key=lambda j: j["order"])]


def _guardar_jugadores(gid: str, jugadores: dict[str, dict], estado: dict) -> None:
    if jugadores:
        redis.hset(k_players(gid), mapping={pid: json.dumps(j, ensure_ascii=False) for pid, j in jugadores.items()})
    redis.expire(k_players(gid), _ttl_estado(estado))


def _respuestas(gid: str, idx: int) -> dict[str, dict]:
    return {pid: json.loads(v) for pid, v in redis.hgetall(k_answers(gid, idx)).items()}


def _emitir(estado: dict, tipo: str, payload: dict | None = None) -> dict:
    return publicar(canal_partida(estado["game_id"]), tipo, estado["game_id"], payload)


# --------------------------------------------------------------- Ranking ----

def _ordenar(jugadores: dict[str, dict]) -> list[dict]:
    """Desempate: mayor puntaje -> menor tiempo total acumulado -> orden de ingreso."""
    lista = sorted(jugadores.values(), key=lambda j: (-j["score"], j["total_time"], j["order"]))
    return [{"pos": i + 1, "player_id": j["player_id"], "name": j["name"], "avatar": j["avatar"],
             "score": j["score"], "total_time": round(j["total_time"], 2)} for i, j in enumerate(lista)]


def _puntos(correcta: bool, transcurrido: float, duracion: int) -> int:
    if not correcta:
        return 0
    puntos = config.BASE_POINTS
    if config.SPEED_BONUS_ENABLED and duracion > 0:
        restante = max(0.0, duracion - transcurrido)
        puntos += round(config.SPEED_BONUS_MAX * restante / duracion)
    return puntos


# ---------------------------------------------------------- Vista pública ----

def _pregunta_publica(estado: dict) -> dict | None:
    """La pregunta en curso sin la respuesta correcta."""
    idx = estado["idx"]
    if idx < 0 or estado["status"] == LOBBY:
        return None
    q = estado["questions"][idx]
    duracion = _duracion_pregunta(q)
    pub = {"idx": idx, "text": q["text"], "options": q["options"],
           "started_at": estado.get("started_at_q"), "deadline": estado.get("deadline"),
           "duration": duracion}
    if q.get("code_block"):
        pub["code_block"] = q["code_block"]
    return pub


def instantanea(gid: str, session_id: str | None = None) -> dict:
    """Estado completo para conectar/reconectar. Nunca incluye la opción correcta de la pregunta abierta."""
    estado = _exigir_estado(gid)
    jugadores = _jugadores(gid)
    ultimo = {k: v for k, v in (estado.get("last") or {}).items() if k != "points"} or None
    vista = {
        "game_id": gid, "title": estado["title"], "category": estado["category"],
        "status": estado["status"], "cancelled": estado.get("cancelled", False),
        "total_questions": estado["total_questions"], "idx": estado["idx"],
        "question": _pregunta_publica(estado),
        "last": ultimo, "ranking": estado.get("ranking"), "podium": estado.get("podium"),
        "created_at": estado["created_at"], "started_at": estado.get("started_at"), "ended_at": estado.get("ended_at"),
        "players": _jugadores_para_evento(gid),
        "server_now": ahora_ms(),
    }
    conteo = _conteo_respuestas(gid, estado["idx"]) if estado["idx"] >= 0 else {"count": 0, "confirmed_count": 0}
    vista["answers_count"], vista["answers_confirmed"] = conteo["count"], conteo["confirmed_count"]
    yo = jugadores.get(session_id) if session_id else None
    if yo:
        posicion = next((r["pos"] for r in _ordenar(jugadores) if r["player_id"] == session_id), None)
        crudo = redis.hget(k_answers(gid, estado["idx"]), session_id) if estado["idx"] >= 0 else None
        respuesta = json.loads(crudo) if crudo else {}
        vista["me"] = {**yo, "position": posicion,
                       "answer": respuesta.get("option"),
                       "answer_confirmed": bool(respuesta.get("confirmed")),
                       "last_points": (estado.get("last") or {}).get("points", {}).get(session_id)}
    else:
        vista["me"] = None
    return vista


# -------------------------------------------------------------- Partida ----

def _cantidad_preguntas_partida(valor) -> int | None:
    """Entero > 0 para tomar N al azar; None significa todas."""
    if valor is None or valor == "":
        return None
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise ErrorJuego("La cantidad de preguntas debe ser un número entero (0 o vacío = todas).")
    if n < 0:
        raise ErrorJuego("La cantidad de preguntas no puede ser negativa.")
    return None if n == 0 else n


def crear_partida(
    category_id: str,
    question_ids: list[str] | None = None,
    question_count: int | None = None,
) -> dict:
    actual = partida_actual_id()
    if actual:
        estado_actual = cargar_estado(actual)
        if estado_actual and estado_actual["status"] != OVER:
            raise ErrorJuego("Ya hay una partida activa. Cancélala o termínala antes de crear otra.", 409)

    categoria = catalogo.obtener_categoria(category_id)
    titulo = categoria["name"]
    cantidad = _cantidad_preguntas_partida(question_count)
    if question_ids and cantidad:
        raise ErrorJuego("Usa la selección manual de preguntas o la cantidad al azar, no ambas.", 400)
    preguntas = catalogo.preguntas_para_partida(category_id, question_ids)
    if cantidad and len(preguntas) > cantidad:
        preguntas = random.sample(preguntas, cantidad)
    if not preguntas:
        raise ErrorJuego("La categoría no tiene preguntas; no se puede lanzar la partida.")
    random.shuffle(preguntas)

    gid = str(ObjectId())
    estado = {
        "game_id": gid, "title": titulo, "category": categoria, "status": LOBBY,
        "questions": preguntas, "question_ids": [q["id"] for q in preguntas], "total_questions": len(preguntas),
        "idx": -1, "created_at": ahora_ms(), "started_at": None, "ended_at": None,
        "last": None, "ranking": None, "podium": None, "cancelled": False,
    }
    guardar_estado(estado)
    redis.delete(k_players(gid))
    redis.set(K_CURRENT, gid)
    comando = publicar(pubsub.CANAL_GLOBAL, "game_created", gid,
                       {"title": titulo, "category": categoria, "total_questions": len(preguntas)})
    return {"game": instantanea(gid), "comandos": [
        (f"SET {k_state(gid)} <json> EX {_ttl_estado(estado)}", "OK"),
        (f"SET {K_CURRENT} {gid}", "OK"),
        (comando["comando"], comando["respuesta"]),
    ]}


def _validar_nombre(nombre: str) -> str:
    nombre = " ".join((nombre or "").split())
    if not config.MIN_NAME_LENGTH <= len(nombre) <= config.MAX_NAME_LENGTH:
        raise ErrorJuego(f"El nombre debe tener entre {config.MIN_NAME_LENGTH} y {config.MAX_NAME_LENGTH} caracteres.")
    return nombre


def unirse(gid: str, session_id: str, nombre: str) -> dict:
    """Un jugador entra al LOBBY. Nombres únicos por partida; tras el inicio solo se es espectador."""
    if not session_id:
        raise ErrorJuego("Falta el identificador de sesión.")
    nombre = _validar_nombre(nombre)
    estado = _exigir_estado(gid)
    jugadores = _jugadores(gid)

    if session_id in jugadores:                                   # reconexión: ya está dentro
        return {"player": jugadores[session_id], "reconnected": True, "game": instantanea(gid, session_id)}
    if estado["status"] != LOBBY:
        raise ErrorJuego("La partida ya comenzó. Entras como espectador hasta la próxima.", 409, spectator=True)
    if any(j["name"].lower() == nombre.lower() for j in jugadores.values()):
        raise ErrorJuego(f"El nombre «{nombre}» ya está en uso en esta partida. Elige otro.", 409, duplicate=True)

    jugador = {
        "player_id": session_id, "name": nombre,
        "avatar": {"shape": random.randrange(AVATAR_FORMAS), "color": random.randrange(AVATAR_COLORES)},
        "score": 0, "total_time": 0.0, "order": len(jugadores) + 1, "joined_at": ahora_ms(),
    }
    redis.hset(k_players(gid), session_id, json.dumps(jugador, ensure_ascii=False))
    redis.expire(k_players(gid), _ttl_estado(estado))
    lista = _jugadores_para_evento(gid)
    _emitir(estado, "player_joined", {"player_id": session_id, "name": nombre, "avatar": jugador["avatar"],
                                      "order": jugador["order"], "players_count": len(lista), "players": lista})
    return {"player": jugador, "reconnected": False, "game": instantanea(gid, session_id)}


def salir(gid: str, session_id: str) -> dict:
    """Solo en LOBBY: el jugador se va (cerró la pestaña). Durante la partida se conserva para reconectar."""
    estado = cargar_estado(gid)
    if not estado or estado["status"] != LOBBY:
        return {"ok": False}
    if redis.hdel(k_players(gid), session_id):
        lista = _jugadores_para_evento(gid)
        _emitir(estado, "player_left", {"player_id": session_id, "players_count": len(lista), "players": lista})
        return {"ok": True, "game": instantanea(gid)}
    return {"ok": False}


def vaciar_sala(gid: str) -> dict:
    """Quita a todos los jugadores del LOBBY (solo antes de lanzar). Todos deben volver a unirse."""
    estado = _exigir_estado(gid)
    if estado["status"] != LOBBY:
        raise ErrorJuego("Solo se puede vaciar la sala antes de lanzar la partida.", 409)
    redis.delete(k_players(gid))
    _emitir(estado, "lobby_cleared", {"players": [], "players_count": 0})
    return {"game": instantanea(gid)}


def _borrar_claves_partida(gid: str) -> None:
    """Elimina estado, jugadores, respuestas y flags de cierre de una partida en Redis."""
    t = _temporizadores.pop(gid, None)
    if t:
        t.cancel()
    patrones = (k_state(gid), k_players(gid), f"game:{gid}:closing:*", f"game:{gid}:answers:*")
    for patron in patrones:
        for clave in redis.scan_iter(match=patron, count=200):
            redis.delete(clave)


def reiniciar_sesion() -> dict:
    """Quita la partida activa, limpia Redis y notifica a todos (excepto acciones del Profesor en el cliente).

    No persiste en MongoDB lo dejado a medias. Los jugadores deben recibir `session_reset` por SSE.
    """
    gid = partida_actual_id()
    comandos: list[tuple[str, str]] = []
    if gid:
        _borrar_claves_partida(gid)
    n_del = redis.delete(K_CURRENT)
    c = publicar(pubsub.CANAL_GLOBAL, "session_reset", None, {"previous_game_id": gid})
    comandos.append((f"DEL {K_CURRENT}", f"(integer) {n_del}"))
    comandos.append((c["comando"], c["respuesta"]))
    return {"ok": True, "previous_game_id": gid, "comandos": comandos}


def iniciar(gid: str) -> dict:
    estado = _exigir_estado(gid)
    if estado["status"] != LOBBY:
        raise ErrorJuego("La partida ya fue lanzada.", 409)
    if redis.hlen(k_players(gid)) == 0:
        raise ErrorJuego("No hay jugadores en la sala todavía.", 409)
    estado["started_at"] = ahora_ms()
    guardar_estado(estado)
    c1 = _emitir(estado, "game_started", {"title": estado["title"], "category": estado["category"],
                                          "total_questions": estado["total_questions"]})
    c2 = _lanzar_pregunta(estado, 0)
    return {"game": instantanea(gid), "comandos": [(c1["comando"], c1["respuesta"]), *c2]}


def _lanzar_pregunta(estado: dict, idx: int) -> list[tuple[str, str]]:
    gid = estado["game_id"]
    ahora = ahora_ms()
    q = estado["questions"][idx]
    duracion = _duracion_pregunta(q)
    estado.update({"status": STARTED, "idx": idx, "started_at_q": ahora,
                   "deadline": ahora + duracion * 1000, "current_duration": duracion})
    guardar_estado(estado)
    redis.delete(k_answers(gid, idx))
    payload = {"idx": idx, "total": estado["total_questions"], "text": q["text"],
               "options": q["options"], "started_at": ahora,
               "deadline": estado["deadline"], "duration": duracion}
    if q.get("code_block"):
        payload["code_block"] = q["code_block"]
    c = _emitir(estado, "question_started", payload)
    _programar(gid, duracion + 0.15, cerrar_pregunta, gid, idx)
    return [(f"SET {k_state(gid)} <json status=QUESTION_STARTED idx={idx}> EX …", "OK"),
            (c["comando"], c["respuesta"])]


def _programar(gid: str, segundos: float, fn, *args) -> None:
    anterior = _temporizadores.pop(gid, None)
    if anterior:
        anterior.cancel()
    t = threading.Timer(max(0.0, segundos), _seguro(fn), args=args)
    t.daemon = True
    _temporizadores[gid] = t
    t.start()


def _seguro(fn):
    def envoltura(*args):
        try:
            fn(*args)
        except Exception:                                  # noqa: BLE001
            log.exception("Error en temporizador %s%s", fn.__name__, args)
    return envoltura


def _conteo_respuestas(gid: str, idx: int) -> dict:
    valores = [json.loads(v) for v in redis.hvals(k_answers(gid, idx))]
    confirmadas = sum(1 for v in valores if v.get("confirmed"))
    return {"count": len(valores), "confirmed_count": confirmadas, "pending_count": len(valores) - confirmadas}


def responder(gid: str, session_id: str, idx: int, opcion: str | None, confirmar: bool = False) -> dict:
    """Selección de respuesta en dos pasos, validada contra el deadline del servidor.

    - opcion + confirmar=False : la deja *pendiente*; puede cambiarse o retirarse (opcion=None).
    - opcion + confirmar=True  : la *confirma*; con ANSWER_POLICY=first ya no se puede cambiar.
    - Al vencer el tiempo cuentan todas las guardadas, pendientes o confirmadas.
    """
    estado = _exigir_estado(gid)
    if estado["status"] != STARTED or estado["idx"] != idx:
        raise ErrorJuego("La pregunta ya no está abierta.", 410)
    ahora = ahora_ms()
    if ahora > estado["deadline"]:
        raise ErrorJuego("Tiempo agotado.", 410)
    if not redis.hexists(k_players(gid), session_id):
        raise ErrorJuego("No estás inscrito en esta partida (eres espectador).", 403, spectator=True)

    clave = k_answers(gid, idx)
    crudo = redis.hget(clave, session_id)
    actual = json.loads(crudo) if crudo else None
    if actual and actual.get("confirmed") and config.ANSWER_POLICY == "first":
        raise ErrorJuego("Ya confirmaste tu respuesta.", 409, already=True)

    if opcion is None:                                          # "No": retira la selección pendiente
        redis.hdel(clave, session_id)
        resultado = {"ok": True, "option": None, "confirmed": False}
    else:
        opcion = str(opcion).lower()
        if opcion not in catalogo.OPCIONES:
            raise ErrorJuego("Opción inválida.")
        redis.hset(clave, session_id, json.dumps({"option": opcion, "ts": ahora, "confirmed": bool(confirmar)}))
        redis.expire(clave, _ttl_estado(estado))
        resultado = {"ok": True, "option": opcion, "confirmed": bool(confirmar)}

    conteo = _conteo_respuestas(gid, idx)
    jugadores_n = redis.hlen(k_players(gid))
    _emitir(estado, "answer_received", {"idx": idx, **conteo, "players_count": jugadores_n})
    if jugadores_n > 0 and conteo["confirmed_count"] >= jugadores_n:
        _programar(gid, 0.2, cerrar_pregunta, gid, idx)
    return {**resultado, **conteo}


def _publicar_ranking(gid: str, idx: int) -> None:
    """Pasa de QUESTION_CLOSED a RANKING_SHOWN y emite el top."""
    est = cargar_estado(gid)
    if not est or est["status"] != CLOSED or est["idx"] != idx:
        return
    es_ultima = idx + 1 >= est["total_questions"]
    est["status"] = RANKING
    guardar_estado(est)
    _emitir(est, "ranking_shown", {"idx": idx, "top10": est["ranking"], "is_last": es_ultima,
                                   "total": est["total_questions"]})
    if config.AUTO_ADVANCE_SECONDS > 0:
        _programar(gid, config.AUTO_ADVANCE_SECONDS, _siguiente_automatico, gid, idx)


def cerrar_pregunta(gid: str, idx: int) -> None:
    """Se ejecuta en el servidor al vencer el deadline: puntúa, publica question_closed y ranking_shown."""
    if not redis.set(f"game:{gid}:closing:{idx}", "1", nx=True, ex=60):   # idempotente
        return
    estado = cargar_estado(gid)
    if not estado or estado["status"] != STARTED or estado["idx"] != idx:
        return

    t = _temporizadores.pop(gid, None)
    if t:
        t.cancel()

    q = estado["questions"][idx]
    duracion = estado.get("current_duration") or _duracion_pregunta(q)
    jugadores = _jugadores(gid)
    respuestas = _respuestas(gid, idx)
    conteo = {o: 0 for o in catalogo.OPCIONES}
    puntos_ronda: dict[str, int] = {}

    for pid, j in jugadores.items():
        r = respuestas.get(pid)
        if r:
            conteo[r["option"]] = conteo.get(r["option"], 0) + 1
            transcurrido = min(max((r["ts"] - estado["started_at_q"]) / 1000, 0.0), duracion)
            pts = _puntos(r["option"] == q["correct"], transcurrido, duracion)
        else:
            transcurrido, pts = duracion, 0
        j["score"] += pts
        j["total_time"] = round(j["total_time"] + transcurrido, 3)
        puntos_ronda[pid] = pts
    _guardar_jugadores(gid, jugadores, estado)

    estado["status"] = CLOSED
    estado["last"] = {"idx": idx, "correct": q["correct"], "counts": conteo, "answered": len(respuestas),
                      "players_count": len(jugadores), "points": puntos_ronda}
    guardar_estado(estado)
    _emitir(estado, "question_closed", {"idx": idx, "correct": q["correct"], "counts": conteo,
                                        "answered": len(respuestas), "players_count": len(jugadores)})

    ranking = _ordenar(jugadores)
    estado["ranking"] = ranking[:config.TOP_N]
    guardar_estado(estado)
    pausa = max(0.0, float(config.RESULT_REVEAL_SECONDS))
    if pausa > 0:
        _programar(gid, pausa, _publicar_ranking, gid, idx)
    else:
        _publicar_ranking(gid, idx)


def _siguiente_automatico(gid: str, idx: int) -> None:
    estado = cargar_estado(gid)
    if estado and estado["status"] == RANKING and estado["idx"] == idx:
        siguiente(gid)


def siguiente(gid: str) -> dict:
    estado = _exigir_estado(gid)
    if estado["status"] != RANKING:
        raise ErrorJuego("Solo se puede avanzar cuando se muestra el ranking.", 409)
    if estado["idx"] + 1 < estado["total_questions"]:
        comandos = _lanzar_pregunta(estado, estado["idx"] + 1)
    else:
        comandos = _finalizar(estado)
    return {"game": instantanea(gid), "comandos": comandos}


def cancelar(gid: str) -> dict:
    estado = _exigir_estado(gid)
    if estado["status"] == OVER:
        raise ErrorJuego("La partida ya terminó.", 409)
    comandos = _finalizar(estado, cancelada=True)
    return {"game": instantanea(gid), "comandos": comandos}


def _finalizar(estado: dict, cancelada: bool = False) -> list[tuple[str, str]]:
    gid = estado["game_id"]
    t = _temporizadores.pop(gid, None)
    if t:
        t.cancel()
    jugadores = _jugadores(gid)
    ranking = _ordenar(jugadores)
    estado.update({"status": OVER, "ended_at": ahora_ms(), "cancelled": cancelada,
                   "ranking": ranking[:config.TOP_N], "podium": [] if cancelada else ranking[:3]})
    guardar_estado(estado)

    # Histórico en MongoDB (el estado en vivo de Redis expira solo).
    mongo.games.insert_one({
        "_id": ObjectId(gid), "title": estado["title"], "category_id": ObjectId(estado["category"]["id"]),
        "category_name": estado["category"]["name"],
        "started_at": _dt(estado.get("started_at")), "ended_at": _dt(estado["ended_at"]),
        "question_ids": [ObjectId(q) for q in estado["question_ids"]],
        "questions_played": 0 if cancelada and estado["idx"] < 0 else estado["idx"] + 1,
        "players_count": len(jugadores), "cancelled": cancelada, "ranking_final": ranking,
    })

    if cancelada:
        c = _emitir(estado, "game_cancelled", {})
    else:
        c = _emitir(estado, "game_over", {"podium": estado["podium"], "ranking": estado["ranking"]})
    return [(f"SET {k_state(gid)} <json status=GAME_OVER> EX …", "OK"),
            ("db.games.insert_one({...ranking_final})", f"ObjectId('{gid}')"),
            (c["comando"], c["respuesta"])]


def _dt(ms: int | None) -> datetime | None:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms else None


def recuperar_temporizadores() -> None:
    """Si el backend se reinició con una pregunta abierta, reprograma su cierre."""
    try:
        gid = partida_actual_id()
        estado = cargar_estado(gid) if gid else None
        if estado and estado["status"] == STARTED:
            restante = (estado["deadline"] - ahora_ms()) / 1000 + 0.15
            _programar(gid, restante, cerrar_pregunta, gid, estado["idx"])
            log.info("Temporizador recuperado para %s (pregunta %s, %.1fs)", gid, estado["idx"], restante)
        elif estado and estado["status"] == CLOSED:
            _programar(gid, max(0.2, float(config.RESULT_REVEAL_SECONDS)), _publicar_ranking, gid, estado["idx"])
            log.info("Ranking pendiente recuperado para %s (pregunta %s)", gid, estado["idx"])
    except Exception:                                      # noqa: BLE001
        log.exception("No se pudieron recuperar los temporizadores")
