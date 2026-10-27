"""Clientes de MongoDB y Redis. Las URIs se leen del fichero .env."""
import os

from dotenv import load_dotenv
from pymongo import MongoClient
from redis import Redis

load_dotenv()

mongo = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"),
                    serverSelectionTimeoutMS=3000)[os.getenv("DB_NAME", "bd-educacion")]

redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                       decode_responses=True)
