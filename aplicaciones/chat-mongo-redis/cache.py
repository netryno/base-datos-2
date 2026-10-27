"""
Widget 1 · Caché de consultas (patrón cache-aside).

    1. GET asignatura:<codigo>            ¿está en Redis?   -> HIT:  responder desde Redis
    2. db.asignatura.find_one(...)        MISS: ir a MongoDB
    3. SET asignatura:<codigo> ... EX 60  guardar en Redis 60 segundos
"""
import json
import time

from conexiones import mongo, redis

TTL = 60  # segundos que vive el dato en Redis


def codigos_asignaturas() -> list[str]:
    return sorted(mongo.asignatura.distinct("codigo"))


def obtener_asignatura(codigo: str) -> dict:
    clave = f"asignatura:{codigo}"
    inicio = time.perf_counter()

    cache = redis.get(clave)                                              # 1
    if cache:
        doc, origen = json.loads(cache), "CACHE"
        comandos = [(f"GET {clave}", json.dumps(cache[:40] + "…", ensure_ascii=False))]
    else:
        doc = mongo.asignatura.find_one({"codigo": codigo}, {"_id": 0, "inscritos": 0})  # 2
        origen = "BD"
        redis.set(clave, json.dumps(doc), ex=TTL)                         # 3
        comandos = [(f"GET {clave}", "(nil)"),
                    (f"db.asignatura.find_one({{codigo: '{codigo}'}})", "→ MongoDB"),
                    (f"SET {clave} <json> EX {TTL}", "OK")]

    ms = round((time.perf_counter() - inicio) * 1000, 2)
    return {"origen": origen, "ms": ms, "doc": doc, "ttl": redis.ttl(clave), "comandos": comandos}


def vaciar_asignatura(codigo: str) -> dict:
    clave = f"asignatura:{codigo}"
    borrados = redis.delete(clave)
    return {"comandos": [(f"DEL {clave}", f"(integer) {borrados}")]}
