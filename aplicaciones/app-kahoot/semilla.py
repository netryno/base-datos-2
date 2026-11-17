"""
Precarga del banco de preguntas desde preguntas.json (idempotente).

Al arrancar, cada categoría y pregunta del fichero se inserta solo si aún no existe
(categoría por nombre, pregunta por categoría + texto). Las que ya están no se tocan.
"""
import json
import logging
import os
from datetime import datetime, timezone

from catalogo import OPCIONES, categorias, preguntas

log = logging.getLogger("semilla")


def _validar(q: dict, categoria: str) -> None:
    texto = q.get("texto", "")
    if not isinstance(texto, str) or not 3 <= len(texto.strip()) <= 300:
        raise ValueError(f"[{categoria}] texto inválido: {texto!r}")
    opciones = q.get("opciones") or {}
    if set(opciones) != set(OPCIONES) or any(not str(opciones[o]).strip() for o in OPCIONES):
        raise ValueError(f"[{categoria}] faltan opciones a/b/c/d en: {texto!r}")
    if q.get("correcta") not in OPCIONES:
        raise ValueError(f"[{categoria}] 'correcta' debe ser a, b, c o d en: {texto!r}")


def precargar(ruta: str | None = None) -> dict:
    ruta = ruta or os.getenv("SEED_FILE", "preguntas.json")
    if not os.path.exists(ruta):
        log.info("Sin fichero de precarga (%s); se omite.", ruta)
        return {"categorias": 0, "preguntas": 0}

    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)

    ahora = datetime.now(timezone.utc)
    nuevas_cat = nuevas_q = 0
    for cat in datos.get("categorias", []):
        nombre = " ".join(str(cat.get("nombre", "")).split())
        if not nombre:
            continue
        res = categorias.update_one(
            {"name_lower": nombre.lower()},
            {"$setOnInsert": {"name": nombre, "name_lower": nombre.lower(), "created_at": ahora}},
            upsert=True,
        )
        nuevas_cat += 1 if res.upserted_id else 0
        cid = res.upserted_id or categorias.find_one({"name_lower": nombre.lower()}, {"_id": 1})["_id"]

        for q in cat.get("preguntas", []):
            _validar(q, nombre)
            texto = " ".join(q["texto"].split())
            doc_insert = {
                "category_id": cid,
                "text": texto,
                "options": {o: str(q["opciones"][o]).strip() for o in OPCIONES},
                "correct": q["correcta"],
                "created_at": ahora,
            }
            if q.get("tiempo_segundos") is not None:
                doc_insert["duration_seconds"] = int(q["tiempo_segundos"])
            bloque = q.get("codigo")
            if isinstance(bloque, str) and bloque.strip():
                doc_insert["code_block"] = {"content": bloque.strip()}
            elif isinstance(bloque, dict) and (bloque.get("contenido") or bloque.get("content")):
                contenido = (bloque.get("contenido") or bloque.get("content") or "").strip()
                if contenido:
                    cb = {"content": contenido}
                    lang = (bloque.get("lenguaje") or bloque.get("language") or "").strip()
                    if lang:
                        cb["language"] = lang
                    doc_insert["code_block"] = cb
            res = preguntas.update_one(
                {"category_id": cid, "text": texto},
                {"$setOnInsert": doc_insert},
                upsert=True,
            )
            nuevas_q += 1 if res.upserted_id else 0

    log.info("Precarga desde %s: %d categorías y %d preguntas nuevas.", ruta, nuevas_cat, nuevas_q)
    return {"categorias": nuevas_cat, "preguntas": nuevas_q}
