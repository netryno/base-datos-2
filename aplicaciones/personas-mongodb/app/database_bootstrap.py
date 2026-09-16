"""
Inicialización de MongoDB (BD + colecciones + índices + semilla) al arrancar la API.
"""
import os
import time

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient, ReturnDocument
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(
            f"Falta la variable de entorno {name}. "
            "Copia .env.example a .env y completa los valores."
        )
    return value


MONGO_URI = _require_env("MONGO_URI")
MONGO_AUTH_SOURCE = os.getenv("MONGO_AUTH_SOURCE", "admin")
DB_NAME = _require_env("DB_NAME")

_client: MongoClient | None = None


def _mongo_uri() -> str:
    separator = "&" if "?" in MONGO_URI else "?"
    return f"{MONGO_URI}{separator}authSource={MONGO_AUTH_SOURCE}"


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(_mongo_uri(), serverSelectionTimeoutMS=5000)
    return _client


def get_database():
    return get_client()[DB_NAME]


def wait_for_server(max_attempts: int = 30, delay_seconds: float = 2.0) -> None:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            get_client().admin.command("ping")
            print(f"[db] Servidor MongoDB disponible (intento {attempt}).")
            return
        except ServerSelectionTimeoutError as exc:
            last_error = exc
            print(f"[db] Esperando MongoDB... ({attempt}/{max_attempts})")
            time.sleep(delay_seconds)
    raise RuntimeError(
        "No se pudo conectar a MongoDB usando MONGO_URI"
    ) from last_error


def ensure_database() -> None:
    db = get_database()
    db.counters.update_one({"_id": "_init"}, {"$setOnInsert": {"ok": True}}, upsert=True)
    print(f"[db] Base de datos '{DB_NAME}' lista (MongoDB la crea al primer uso).")


PAISES_SEED = [
    {"pais_id": 1, "pais_nombre": "Bolivia", "pais_codigo": "BOL"},
    {"pais_id": 2, "pais_nombre": "Argentina", "pais_codigo": "ARG"},
    {"pais_id": 3, "pais_nombre": "Brasil", "pais_codigo": "BRA"},
    {"pais_id": 4, "pais_nombre": "Chile", "pais_codigo": "CHL"},
    {"pais_id": 5, "pais_nombre": "Peru", "pais_codigo": "PER"},
    {"pais_id": 6, "pais_nombre": "Colombia", "pais_codigo": "COL"},
    {"pais_id": 7, "pais_nombre": "Ecuador", "pais_codigo": "ECU"},
    {"pais_id": 8, "pais_nombre": "Paraguay", "pais_codigo": "PRY"},
    {"pais_id": 9, "pais_nombre": "Uruguay", "pais_codigo": "URY"},
    {"pais_id": 10, "pais_nombre": "Venezuela", "pais_codigo": "VEN"},
    {"pais_id": 11, "pais_nombre": "Mexico", "pais_codigo": "MEX"},
    {"pais_id": 12, "pais_nombre": "Estados Unidos", "pais_codigo": "USA"},
    {"pais_id": 13, "pais_nombre": "Espana", "pais_codigo": "ESP"},
    {"pais_id": 14, "pais_nombre": "Francia", "pais_codigo": "FRA"},
    {"pais_id": 15, "pais_nombre": "Alemania", "pais_codigo": "DEU"},
    {"pais_id": 16, "pais_nombre": "Italia", "pais_codigo": "ITA"},
    {"pais_id": 17, "pais_nombre": "Japon", "pais_codigo": "JPN"},
    {"pais_id": 18, "pais_nombre": "China", "pais_codigo": "CHN"},
    {"pais_id": 19, "pais_nombre": "Australia", "pais_codigo": "AUS"},
    {"pais_id": 20, "pais_nombre": "Canada", "pais_codigo": "CAN"},
]


def init_collections() -> None:
    db = get_database()
    existing = set(db.list_collection_names())

    for name in ("paises", "personas", "viajes", "counters"):
        if name not in existing:
            db.create_collection(name)
            print(f"[db] Colección '{name}' creada.")

    db.paises.create_index([("pais_id", ASCENDING)], unique=True)
    db.personas.create_index([("persona_id", ASCENDING)], unique=True)
    db.personas.create_index([("ci", ASCENDING)], unique=True)
    db.viajes.create_index([("viaje_id", ASCENDING)], unique=True)
    db.viajes.create_index([("persona_id", ASCENDING)])
    db.viajes.create_index([("pais_id", ASCENDING)])
    print("[db] Colecciones e índices verificados.")


def seed_paises() -> None:
    db = get_database()
    total = db.paises.count_documents({})
    if total == 0:
        db.paises.insert_many(PAISES_SEED)
        print(f"[seed] Se insertaron {len(PAISES_SEED)} países (Bolivia primero).")
    else:
        print(f"[seed] La colección paises ya tiene {total} documentos. No se insertó nada.")


def next_sequence(db, name: str) -> int:
    doc = db.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc["seq"])


def bootstrap_database() -> None:
    wait_for_server()
    ensure_database()
    try:
        init_collections()
    except OperationFailure as exc:
        raise RuntimeError(
            "No se pudieron crear colecciones/índices. Revisa permisos del usuario MongoDB."
        ) from exc
    seed_paises()
