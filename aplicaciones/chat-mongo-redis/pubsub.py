"""
Widgets 2 y 3 · Publicador / Suscriptores con Redis.

  Lock  : SET lock:publicador <token> NX EX 30   -> solo un publicador a la vez
  Enviar: PUBLISH chat:sala1 "Ficha A-12"        -> devuelve cuántos oyentes lo recibieron
  Oír   : SUBSCRIBE chat:sala1 mapa:sala1        -> los mensajes llegan al navegador por SSE
"""
import json
from typing import Iterator

from conexiones import redis

LOCK = "lock:publicador"
LOCK_TTL = 30                      # segundos; el publicador lo renueva cada 10 s
CANALES = ("chat:sala1", "mapa:sala1")


# ----------------------------------------------------------------- Lock ----

def adquirir_lock(token: str) -> bool:
    """SET NX: solo tiene éxito si la clave no existe. Reentrante para el mismo token."""
    return bool(redis.set(LOCK, token, nx=True, ex=LOCK_TTL)) or redis.get(LOCK) == token


def renovar_lock(token: str) -> int:
    """EXPIRE: extiende la vida del lock. Devuelve el TTL restante o -2 si lo perdió."""
    if redis.get(LOCK) == token:
        redis.expire(LOCK, LOCK_TTL)
    return redis.ttl(LOCK)


def liberar_lock(token: str) -> None:
    if redis.get(LOCK) == token:
        redis.delete(LOCK)


def estado_lock() -> dict:
    return {"ocupado": redis.exists(LOCK) == 1, "ttl": redis.ttl(LOCK)}


# --------------------------------------------------------------- Pub/Sub ----

def publicar(token: str, canal: str, mensaje: str | dict) -> dict:
    if canal not in CANALES or redis.get(LOCK) != token:
        return {"error": "No eres el publicador activo o el canal no existe."}
    texto = json.dumps(mensaje, ensure_ascii=False)
    oyentes = redis.publish(canal, texto)
    return {"oyentes": oyentes, "comando": f"PUBLISH {canal} {texto}"}


def escuchar() -> Iterator[str]:
    """Generador SSE: cada mensaje de Redis se reenvía al navegador como un evento."""
    ps = redis.pubsub(ignore_subscribe_messages=True)
    ps.subscribe(*CANALES)
    try:
        while True:
            m = ps.get_message(timeout=15)
            if m is None:
                yield ": ping\n\n"                     # mantiene viva la conexión
            else:
                yield f"event: {m['channel']}\ndata: {m['data']}\n\n"
    finally:
        ps.close()
