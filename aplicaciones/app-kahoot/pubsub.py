"""
Profesor / Publicador y Pub/Sub con Redis.

  Lock    : SET publisher:lock <json> NX EX 15   -> solo un Profesor a la vez
  Latido  : EXPIRE publisher:lock 15              -> el navegador lo renueva cada 5 s
  Emitir  : PUBLISH game:<id>:events <json>       -> un canal por partida
  Oír     : SUBSCRIBE games:events game:<id>:events -> los mensajes llegan al navegador por SSE

Todos los mensajes son JSON con { type, game_id, ts, payload }.
"""
import json
import time
from typing import Iterable, Iterator

import config
from conexiones import redis

LOCK = "publisher:lock"
CANAL_GLOBAL = "games:events"          # avisos que no pertenecen a una partida (p. ej. game_created)

# Eventos que solo debe recibir el Profesor.
SOLO_PROFESOR = {"answer_received"}


def canal_partida(game_id: str) -> str:
    return f"game:{game_id}:events"


def ahora_ms() -> int:
    return int(time.time() * 1000)


# ----------------------------------------------------------------- Lock ----

def _leer_lock() -> dict | None:
    crudo = redis.get(LOCK)
    try:
        return json.loads(crudo) if crudo else None
    except json.JSONDecodeError:
        return None


def reclamar_lock(session_id: str, nombre: str) -> dict:
    """SET NX: solo tiene éxito si la clave no existe. Reentrante para la misma sesión."""
    valor = {"session_id": session_id, "name": nombre, "acquired_at": ahora_ms()}
    ok = bool(redis.set(LOCK, json.dumps(valor, ensure_ascii=False), nx=True, ex=config.PUBLISHER_LOCK_TTL))
    if not ok:
        actual = _leer_lock()
        if actual and actual.get("session_id") == session_id:      # misma pestaña: renueva y sigue
            redis.expire(LOCK, config.PUBLISHER_LOCK_TTL)
            ok, valor = True, actual
    return {
        "ok": ok,
        "ttl": redis.ttl(LOCK),
        "lock": valor if ok else _leer_lock(),
        "comando": f"SET {LOCK} <json> NX EX {config.PUBLISHER_LOCK_TTL}",
        "respuesta": "OK" if ok else "(nil)",
    }


def renovar_lock(session_id: str) -> int:
    """EXPIRE: extiende la vida del lock. Devuelve el TTL restante o -2 si lo perdió."""
    if es_profesor(session_id):
        redis.expire(LOCK, config.PUBLISHER_LOCK_TTL)
        return redis.ttl(LOCK)
    return -2


def liberar_lock(session_id: str) -> bool:
    if es_profesor(session_id):
        redis.delete(LOCK)
        return True
    return False


def es_profesor(session_id: str) -> bool:
    actual = _leer_lock()
    return bool(session_id) and bool(actual) and actual.get("session_id") == session_id


def estado_lock() -> dict:
    actual = _leer_lock()
    return {
        "ocupado": actual is not None,
        "ttl": redis.ttl(LOCK),
        "nombre": actual.get("name") if actual else None,
    }


# --------------------------------------------------------------- Pub/Sub ----

def publicar(canal: str, tipo: str, game_id: str | None, payload: dict | None = None) -> dict:
    """PUBLISH: emite un evento del contrato y devuelve cuántos oyentes lo recibieron."""
    mensaje = {"type": tipo, "game_id": game_id, "ts": ahora_ms(), "payload": payload or {}}
    texto = json.dumps(mensaje, ensure_ascii=False)
    oyentes = redis.publish(canal, texto)
    return {"oyentes": oyentes, "comando": f"PUBLISH {canal} {tipo}", "respuesta": f"(integer) {oyentes}"}


def sse(tipo: str, data: dict | str) -> str:
    """Formatea un evento Server-Sent Events."""
    texto = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {tipo}\ndata: {texto}\n\n"


def _relleno_proxy() -> str:
    """Comentario SSE ~4 KiB: muchos proxies (p. ej. Cloudflare) no reenvían el stream hasta tener un bloque grande."""
    return f": {' ' * 4088}\n\n"


def escuchar(canales: Iterable[str], rol: str, inicial: Iterable[str] = ()) -> Iterator[str]:
    """Generador SSE: cada mensaje de Redis se reenvía al navegador como un evento.

    `inicial` son eventos ya formateados (p. ej. el state_snapshot) que se envían antes de escuchar.
    """
    ps = redis.pubsub(ignore_subscribe_messages=True)
    ps.subscribe(*canales)
    try:
        yield _relleno_proxy()
        for e in inicial:
            yield e
        yield sse("subscribed", {"canales": list(canales)})
        ping_s = max(1, config.SSE_PING_INTERVAL)
        while True:
            m = ps.get_message(timeout=ping_s)
            if m is None:
                yield ": ping\n\n"                              # mantiene viva la conexión (crítico tras túneles/proxy)
                continue
            try:
                tipo = json.loads(m["data"]).get("type", "message")
            except (json.JSONDecodeError, TypeError, AttributeError):
                tipo = "message"
            if tipo in SOLO_PROFESOR and rol != "profesor":
                continue
            yield sse(tipo, m["data"])
    finally:
        ps.close()
