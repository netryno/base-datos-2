"""
Banco de preguntas en MongoDB.

  categories : { _id, name }
  questions  : { _id, category_id, text, options: {a,b,c,d}, correct, created_at }
"""
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING

from conexiones import mongo

OPCIONES = ("a", "b", "c", "d")

categorias = mongo.categories
preguntas = mongo.questions


class ErrorCatalogo(Exception):
    def __init__(self, mensaje: str, codigo: int = 400):
        super().__init__(mensaje)
        self.codigo = codigo


def preparar_indices() -> None:
    categorias.create_index([("name_lower", ASCENDING)], unique=True)
    preguntas.create_index([("category_id", ASCENDING)])


def _oid(valor: str, que: str) -> ObjectId:
    try:
        return ObjectId(valor)
    except (InvalidId, TypeError):
        raise ErrorCatalogo(f"Identificador de {que} inválido.") from None


# ------------------------------------------------------------ Categorías ----

def _categoria_publica(doc: dict, total: int | None = None) -> dict:
    salida = {"id": str(doc["_id"]), "name": doc["name"]}
    if total is not None:
        salida["questions"] = total
    return salida


def listar_categorias() -> list[dict]:
    conteo = {c["_id"]: c["n"] for c in preguntas.aggregate([{"$group": {"_id": "$category_id", "n": {"$sum": 1}}}])}
    return [_categoria_publica(c, conteo.get(c["_id"], 0)) for c in categorias.find().sort("name", ASCENDING)]


def obtener_categoria(category_id: str) -> dict:
    doc = categorias.find_one({"_id": _oid(category_id, "categoría")})
    if not doc:
        raise ErrorCatalogo("La categoría no existe.", 404)
    return _categoria_publica(doc)


def crear_categoria(nombre: str) -> dict:
    nombre = (nombre or "").strip()
    if not 1 <= len(nombre) <= 60:
        raise ErrorCatalogo("El nombre de la categoría debe tener entre 1 y 60 caracteres.")
    if categorias.find_one({"name_lower": nombre.lower()}):
        raise ErrorCatalogo("Ya existe una categoría con ese nombre.", 409)
    res = categorias.insert_one({"name": nombre, "name_lower": nombre.lower(),
                                 "created_at": datetime.now(timezone.utc)})
    return {"id": str(res.inserted_id), "name": nombre, "questions": 0}


def eliminar_categoria(category_id: str) -> dict:
    oid = _oid(category_id, "categoría")
    if preguntas.count_documents({"category_id": oid}) > 0:
        raise ErrorCatalogo("La categoría tiene preguntas; elimínalas primero.", 409)
    if categorias.delete_one({"_id": oid}).deleted_count == 0:
        raise ErrorCatalogo("La categoría no existe.", 404)
    return {"ok": True}


# ------------------------------------------------------------- Preguntas ----

def _pregunta_publica(doc: dict) -> dict:
    salida = {
        "id": str(doc["_id"]),
        "category_id": str(doc["category_id"]),
        "text": doc["text"],
        "options": doc["options"],
        "correct": doc["correct"],
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
    }
    if doc.get("duration_seconds") is not None:
        salida["duration_seconds"] = int(doc["duration_seconds"])
    if doc.get("code_block"):
        salida["code_block"] = doc["code_block"]
    return salida


def listar_preguntas(category_id: str | None = None) -> list[dict]:
    filtro = {"category_id": _oid(category_id, "categoría")} if category_id else {}
    return [_pregunta_publica(p) for p in preguntas.find(filtro).sort("created_at", ASCENDING)]


def preguntas_para_partida(category_id: str, question_ids: list[str] | None = None) -> list[dict]:
    """Preguntas de la categoría (todas o el subconjunto elegido), con la respuesta correcta."""
    filtro = {"category_id": _oid(category_id, "categoría")}
    if question_ids:
        filtro["_id"] = {"$in": [_oid(q, "pregunta") for q in question_ids]}
    return [_pregunta_publica(p) for p in preguntas.find(filtro)]


def _normalizar_codigo(bloque) -> dict | None:
    if not bloque or not isinstance(bloque, dict):
        return None
    contenido = (bloque.get("content") or "").strip()
    if not contenido:
        return None
    if len(contenido) > 4000:
        raise ErrorCatalogo("El bloque de código no puede superar 4000 caracteres.")
    lenguaje = (bloque.get("language") or "").strip()[:40] or None
    out = {"content": contenido}
    if lenguaje:
        out["language"] = lenguaje
    return out


def crear_pregunta(
    category_id: str,
    texto: str,
    opciones: dict,
    correcta: str,
    duration_seconds=None,
    code_block=None,
) -> dict:
    texto = (texto or "").strip()
    if not 3 <= len(texto) <= 300:
        raise ErrorCatalogo("El texto de la pregunta debe tener entre 3 y 300 caracteres.")
    opciones = {k: str((opciones or {}).get(k, "")).strip() for k in OPCIONES}
    if any(not v for v in opciones.values()):
        raise ErrorCatalogo("Las cuatro opciones (a, b, c, d) son obligatorias.")
    if any(len(v) > 120 for v in opciones.values()):
        raise ErrorCatalogo("Cada opción debe tener como máximo 120 caracteres.")
    correcta = (correcta or "").strip().lower()
    if correcta not in OPCIONES:
        raise ErrorCatalogo("Debes marcar una única opción correcta (a, b, c o d).")
    duracion = None
    if duration_seconds is not None and str(duration_seconds).strip() != "":
        try:
            duracion = int(duration_seconds)
        except (TypeError, ValueError):
            raise ErrorCatalogo("El tiempo de respuesta debe ser un número entero de segundos.") from None
        if not 5 <= duracion <= 300:
            raise ErrorCatalogo("El tiempo de respuesta debe estar entre 5 y 300 segundos.")
    bloque = _normalizar_codigo(code_block)
    cat_oid = _oid(category_id, "categoría")
    if not categorias.find_one({"_id": cat_oid}):
        raise ErrorCatalogo("La categoría no existe.", 404)
    doc = {"category_id": cat_oid, "text": texto, "options": opciones, "correct": correcta,
           "created_at": datetime.now(timezone.utc)}
    if duracion is not None:
        doc["duration_seconds"] = duracion
    if bloque:
        doc["code_block"] = bloque
    doc["_id"] = preguntas.insert_one(doc).inserted_id
    return _pregunta_publica(doc)


def eliminar_pregunta(question_id: str) -> dict:
    if preguntas.delete_one({"_id": _oid(question_id, "pregunta")}).deleted_count == 0:
        raise ErrorCatalogo("La pregunta no existe.", 404)
    return {"ok": True}
