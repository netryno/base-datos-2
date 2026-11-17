"""Clientes de MongoDB y Redis. Las URIs se leen del fichero .env."""
import os

from dotenv import load_dotenv
from pymongo import MongoClient
from redis import Redis

load_dotenv()

mongo = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"),
                    serverSelectionTimeoutMS=3000)[os.getenv("DB_NAME", "bd-kahoot")]

redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                       decode_responses=True, socket_connect_timeout=3)


def salud() -> dict:
    """Estado de ambas conexiones: la app queda 'degradada' si Redis no responde."""
    estado = {"redis": "ok", "mongo": "ok"}
    try:
        redis.ping()
    except Exception as e:                      # noqa: BLE001
        estado["redis"] = f"down: {e.__class__.__name__}"
    try:
        mongo.command("ping")
    except Exception as e:                      # noqa: BLE001
        estado["mongo"] = f"down: {e.__class__.__name__}"
    return estado
