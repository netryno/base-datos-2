"""
Tutorial: Python + SQLite - Seeder para pruebas de JOINs
"""

import os
import sqlite3
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime, timedelta
import random
import uuid

# ============================================================================
# CONEXIÓN A SQLITE
# ============================================================================

DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/personas.db")

def init_db():
    """Crea las tablas si no existen (esquema)."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS paises (
            pais_id      INTEGER PRIMARY KEY,
            pais_nombre  VARCHAR(50) NOT NULL,
            pais_codigo  VARCHAR(5)  NOT NULL
        );

        CREATE TABLE IF NOT EXISTS personas (
            persona_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre           VARCHAR(50) NOT NULL,
            primer_apellido  VARCHAR(50) NOT NULL,
            segundo_apellido VARCHAR(50),
            ci               VARCHAR(20) NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS viajes (
            viaje_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            persona_id    INTEGER NOT NULL,
            pais_id       INTEGER NOT NULL,
            fecha_llegada DATE NOT NULL,
            FOREIGN KEY (persona_id) REFERENCES personas(persona_id),
            FOREIGN KEY (pais_id)    REFERENCES paises(pais_id)
        );

        CREATE INDEX IF NOT EXISTS idx_viajes_persona ON viajes(persona_id);
        CREATE INDEX IF NOT EXISTS idx_viajes_pais    ON viajes(pais_id);
    """)
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


# ============================================================================
# MODELOS PYDANTIC (validación de entrada)
# ============================================================================

class PersonaCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=50)
    primer_apellido: str = Field(..., min_length=1, max_length=50)
    segundo_apellido: Optional[str] = Field(None, max_length=50)
    ci: str = Field(..., min_length=1, max_length=20)

    @field_validator('ci')
    @classmethod
    def ci_solo_numeros(cls, v):
        if not v.isdigit():
            raise ValueError('CI debe contener solo numeros')
        return v


class ViajeCreate(BaseModel):
    persona_id: int = Field(..., gt=0)
    pais_id: int = Field(..., gt=0)
    fecha_llegada: date = Field(...)

    @field_validator('fecha_llegada')
    @classmethod
    def no_futuro(cls, v):
        if v > date.today():
            raise ValueError('La fecha no puede ser futura')
        return v


# ============================================================================
# FASTAPI
# ============================================================================

app = FastAPI(
    title="Seeder para pruebas de JOINs (SQLite)",
    description="Genera datos realistas para explicar LEFT/RIGHT/INNER JOIN y performance",
    version="2.0"
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def root():
    return {
        "mensaje": "Seeder API (SQLite) - Usa POST /seed para generar datos",
        "ejemplo": "/seed?n_personas=100&viajes_por_persona=3"
    }


# ============================================================================
# SEEDER - Generador de datos
# ============================================================================

NOMBRES = [
    "Juan", "Maria", "Carlos", "Ana", "Luis", "Carmen", "Pedro", "Laura",
    "Jose", "Sofia", "Miguel", "Isabel", "Antonio", "Elena", "Francisco",
    "Lucia", "Javier", "Paula", "Manuel", "Martina", "Daniel", "Valentina",
    "Alejandro", "Camila", "Diego", "Mariana", "Fernando", "Daniela", "Andres"
]

APELLIDOS = [
    "Garcia", "Rodriguez", "Lopez", "Martinez", "Perez", "Gonzalez", "Sanchez",
    "Romero", "Fernandez", "Torres", "Ramirez", "Flores", "Rivera", "Castro",
    "Morales", "Ortega", "Delgado", "Rojas", "Vargas", "Silva", "Mendoza", "Ruiz"
]

PAISES = [
    (1, "Bolivia", "BOL"), (2, "Argentina", "ARG"), (3, "Brasil", "BRA"),
    (4, "Chile", "CHL"), (5, "Peru", "PER"), (6, "Colombia", "COL"),
    (7, "Mexico", "MEX"), (8, "Espana", "ESP"), (9, "Estados Unidos", "USA"),
    (10, "Francia", "FRA"), (11, "Alemania", "DEU"), (12, "Italia", "ITA"),
    (13, "Japon", "JPN"), (14, "China", "CHN"), (15, "Australia", "AUS")
]


def generar_ci() -> str:
    return str(uuid.uuid4().int)[:12]  # 12 dígitos únicos


def generar_fecha() -> date:
    inicio = datetime(2015, 1, 1)
    fin = datetime.now()
    dias = random.randint(0, (fin - inicio).days)
    return (inicio + timedelta(days=dias)).date()


@app.post("/seed", status_code=201)
def seed_data(
    n_personas: int = 100,
    viajes_por_persona: int = 3,
    db=Depends(get_db)
):
    """
    Genera N personas y X viajes por persona.

    Ejemplos:
        POST /seed?n_personas=100&viajes_por_persona=3
        POST /seed?n_personas=1000&viajes_por_persona=5
        POST /seed?n_personas=50&viajes_por_persona=0   (solo personas, sin viajes)
    """
    cursor = db.cursor()
    personas_insertadas = 0
    viajes_insertados = 0

    try:
        # Insertar paises si no existen
        cursor.execute("SELECT COUNT(*) FROM paises")
        if cursor.fetchone()['COUNT(*)'] == 0:
            for pais_id, nombre, codigo in PAISES:
                cursor.execute(
                    "INSERT INTO paises (pais_id, pais_nombre, pais_codigo) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                    (pais_id, nombre, codigo)
                )
            db.commit()

        # Generar personas y sus viajes
        for i in range(n_personas):
            nombre = random.choice(NOMBRES)
            apellido1 = random.choice(APELLIDOS)
            apellido2 = random.choice(APELLIDOS) if random.random() > 0.3 else None
            ci = generar_ci()

            cursor.execute(
                """
                INSERT INTO personas (nombre, primer_apellido, segundo_apellido, ci)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (ci) DO NOTHING
                RETURNING persona_id
                """,
                (nombre, apellido1, apellido2, ci)
            )

            resultado = cursor.fetchone()
            if resultado:
                personas_insertadas += 1
                persona_id = resultado['persona_id']

                # Viajes aleatorios para esta persona (0 hasta viajes_por_persona * 2)
                n_viajes = random.randint(0, viajes_por_persona * 2)

                for _ in range(n_viajes):
                    pais_id = random.choice(PAISES)[0]
                    fecha = generar_fecha()

                    cursor.execute(
                        "INSERT INTO viajes (persona_id, pais_id, fecha_llegada) VALUES (?, ?, ?)",
                        (persona_id, pais_id, fecha.isoformat())
                    )
                    viajes_insertados += 1

        db.commit()

        # Estadisticas
        cursor.execute("SELECT COUNT(*) as total FROM personas")
        total_personas = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as total FROM viajes")
        total_viajes = cursor.fetchone()['total']

        cursor.execute("""
            SELECT COUNT(DISTINCT persona_id) as con_viajes
            FROM viajes
        """)
        con_viajes = cursor.fetchone()['con_viajes']

        return {
            "insertados": {
                "personas_nuevas": personas_insertadas,
                "viajes_nuevos": viajes_insertados
            },
            "totales_en_bd": {
                "personas": total_personas,
                "viajes": total_viajes
            },
            "personas_sin_viajes": total_personas - con_viajes,
            "nota": "Personas sin viajes sirven para demostrar LEFT JOIN"
        }

    except sqlite3.Error as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        cursor.close()
