"""
Inicialización de PostgreSQL (BD + tablas + semilla) al arrancar la API.
Módulo aparte para no cargar FastAPI/openpyxl durante el bootstrap.
"""
import os
import time

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise RuntimeError(
            f"Falta la variable de entorno {name}. "
            "Copia .env.example a .env y completa los valores."
        )
    return value


DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = _require_env("DB_USER")
DB_PASSWORD = _require_env("DB_PASSWORD")
DB_NAME = _require_env("DB_NAME")
MAINTENANCE_DB = os.getenv("DB_MAINTENANCE", "postgres")


def get_connection(database: str | None = None):
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=database or DB_NAME,
    )


def wait_for_server(max_attempts: int = 30, delay_seconds: float = 2.0) -> None:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            conn = get_connection(database=MAINTENANCE_DB)
            conn.close()
            print(
                f"[db] Servidor PostgreSQL disponible en "
                f"{DB_HOST}:{DB_PORT} (intento {attempt})."
            )
            return
        except psycopg2.OperationalError as exc:
            last_error = exc
            print(f"[db] Esperando PostgreSQL... ({attempt}/{max_attempts})")
            time.sleep(delay_seconds)
    raise RuntimeError(
        f"No se pudo conectar a PostgreSQL en {DB_HOST}:{DB_PORT}"
    ) from last_error


def ensure_database() -> None:
    try:
        conn = get_connection(database=DB_NAME)
        conn.close()
        print(f"[db] Base de datos '{DB_NAME}' accesible.")
        return
    except psycopg2.OperationalError:
        pass

    conn = get_connection(database=MAINTENANCE_DB)
    conn.autocommit = True
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (DB_NAME,),
        )
        if cursor.fetchone() is None:
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME))
            )
            print(f"[db] Base de datos '{DB_NAME}' creada.")
        else:
            print(f"[db] Base de datos '{DB_NAME}' ya existe.")
    except psycopg2.Error as exc:
        raise RuntimeError(
            f"No se pudo usar ni crear la base '{DB_NAME}'. "
            "Revisa DB_NAME en .env y que my-database esté en marcha."
        ) from exc
    finally:
        cursor.close()
        conn.close()


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS paises (
        pais_id      INT PRIMARY KEY,
        pais_nombre  VARCHAR(50) NOT NULL,
        pais_codigo  VARCHAR(5)  NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS personas (
        persona_id       SERIAL PRIMARY KEY,
        nombre           VARCHAR(50) NOT NULL,
        primer_apellido  VARCHAR(50) NOT NULL,
        segundo_apellido VARCHAR(50),
        ci               VARCHAR(20) NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS viajes (
        viaje_id      SERIAL PRIMARY KEY,
        persona_id    INT NOT NULL,
        pais_id       INT NOT NULL,
        fecha_llegada DATE NOT NULL,
        FOREIGN KEY (persona_id) REFERENCES personas(persona_id) ON DELETE CASCADE,
        FOREIGN KEY (pais_id)    REFERENCES paises(pais_id)    ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_viajes_persona ON viajes(persona_id)",
    "CREATE INDEX IF NOT EXISTS idx_viajes_pais ON viajes(pais_id)",
]

PAISES_SEED = [
    (1,  "Bolivia",         "BOL"),
    (2,  "Argentina",       "ARG"),
    (3,  "Brasil",           "BRA"),
    (4,  "Chile",            "CHL"),
    (5,  "Peru",             "PER"),
    (6,  "Colombia",         "COL"),
    (7,  "Ecuador",          "ECU"),
    (8,  "Paraguay",         "PRY"),
    (9,  "Uruguay",          "URY"),
    (10, "Venezuela",        "VEN"),
    (11, "Mexico",           "MEX"),
    (12, "Estados Unidos",   "USA"),
    (13, "Espana",           "ESP"),
    (14, "Francia",          "FRA"),
    (15, "Alemania",         "DEU"),
    (16, "Italia",           "ITA"),
    (17, "Japon",            "JPN"),
    (18, "China",            "CHN"),
    (19, "Australia",        "AUS"),
    (20, "Canada",           "CAN"),
]


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        for stmt in SCHEMA_STATEMENTS:
            cursor.execute(stmt)
        conn.commit()
        print("[db] Esquema verificado (tablas e índices).")
    finally:
        cursor.close()
        conn.close()


def seed_paises() -> None:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT COUNT(*) AS total FROM paises")
        total = cursor.fetchone()["total"]
        if total == 0:
            cursor.executemany(
                "INSERT INTO paises (pais_id, pais_nombre, pais_codigo) VALUES (%s, %s, %s)",
                PAISES_SEED,
            )
            conn.commit()
            print(f"[seed] Se insertaron {len(PAISES_SEED)} países (Bolivia primero).")
        else:
            print(f"[seed] La tabla paises ya tiene {total} registros. No se insertó nada.")
    finally:
        cursor.close()
        conn.close()


def bootstrap_database() -> None:
    wait_for_server()
    ensure_database()
    init_db()
    seed_paises()
