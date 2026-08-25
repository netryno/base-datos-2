"""
===========================================================================
Python + SQL Server con FastAPI
===========================================================================

Este archivo es INTENCIONALMENTE monolítico para que veas todo el flujo
de conexión a base de datos en un solo lugar.

FLUJO DE CONEXIÓN:
1. pyodbc → Driver que habla con SQL Server usando el ODBC de Microsoft.
2. Variables de entorno → HOST, PORT, USER, PASSWORD, DATABASE.
3. get_db() → Función que crea y cierra conexiones.
4. SQL directo → Queries crudos para ver exactamente qué se ejecuta.

DIFERENCIAS CLAVE CON MYSQL:
- SQL Server no tiene CREATE TABLE IF NOT EXISTS: usamos IF OBJECT_ID(...).
- Placeholders: ?  (en vez de %s de MySQL).
- AUTO_INCREMENT → IDENTITY(1,1).
- lastrowid no es confiable: usamos OUTPUT INSERTED.* para devolver la fila.
- ENGINE=InnoDB no existe (las FK siempre se respetan).
- Si la BD no existe, se crea automáticamente al arrancar.
"""

import os
import pyodbc
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date
import re

# ============================================================================
# CONFIGURACIÓN DE CONEXIÓN
# ============================================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "1433")
DB_USER = os.getenv("DB_USER", "sa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "AlumnoSql2025!")
DB_NAME = os.getenv("DB_NAME", "bd_personas")

# Driver ODBC 18 (instalado en el Dockerfile).
DRIVER = "ODBC Driver 18 for SQL Server"


def conn_str(database: str) -> str:
    """
    Construye la cadena de conexión ODBC.
    TrustServerCertificate=yes evita el error de certificado
    cuando el SQL Server usa un certificado autofirmado (caso común
    en contenedores docker).
    """
    return (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={DB_HOST},{DB_PORT};"
        f"UID={DB_USER};PWD={DB_PASSWORD};"
        f"DATABASE={database};"
        f"TrustServerCertificate=yes;Encrypt=yes"
    )


def get_connection(database: str = DB_NAME):
    """Crea y devuelve una conexión a SQL Server."""
    return pyodbc.connect(conn_str(database), autocommit=False)


# ============================================================================
# CREACIÓN DE LA BASE DE DATO Y LAS TABLAS
# ============================================================================

SCHEMA_STATEMENTS = [
    """
    IF OBJECT_ID('dbo.paises', 'U') IS NULL
    CREATE TABLE paises (
        pais_id      INT PRIMARY KEY,
        pais_nombre  VARCHAR(50) NOT NULL,
        pais_codigo  VARCHAR(5)  NOT NULL
    )
    """,
    """
    IF OBJECT_ID('dbo.personas', 'U') IS NULL
    CREATE TABLE personas (
        persona_id       INT PRIMARY KEY IDENTITY(1,1),
        nombre           VARCHAR(50) NOT NULL,
        primer_apellido  VARCHAR(50) NOT NULL,
        segundo_apellido VARCHAR(50),
        ci               VARCHAR(20) NOT NULL UNIQUE
    )
    """,
    """
    IF OBJECT_ID('dbo.viajes', 'U') IS NULL
    CREATE TABLE viajes (
        viaje_id      INT PRIMARY KEY IDENTITY(1,1),
        persona_id    INT NOT NULL,
        pais_id       INT NOT NULL,
        fecha_llegada DATE NOT NULL,
        FOREIGN KEY (persona_id) REFERENCES personas(persona_id) ON DELETE CASCADE,
        FOREIGN KEY (pais_id)    REFERENCES paises(pais_id)    ON DELETE CASCADE
    )
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_viajes_persona')
    CREATE INDEX idx_viajes_persona ON viajes(persona_id)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_viajes_pais')
    CREATE INDEX idx_viajes_pais ON viajes(pais_id)
    """,
]


def init_db():
    """
    Crea la base de datos si no existe y luego las tablas.
    Se ejecuta una vez al iniciar la app.
    """
    # 1. Conectar a 'master' (con autocommit) para poder ejecutar CREATE DATABASE.
    conn = pyodbc.connect(conn_str("master"), autocommit=True)
    cursor = conn.cursor()
    cursor.execute(
        "IF DB_ID(?) IS NULL CREATE DATABASE " + DB_NAME,
        (DB_NAME,)
    )
    cursor.close()
    conn.close()

    # 2. Conectar a nuestra base de datos y crear las tablas.
    conn = get_connection()
    cursor = conn.cursor()
    try:
        for stmt in SCHEMA_STATEMENTS:
            cursor.execute(stmt)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# SEMILLA DE PAÍSES (se ejecuta una sola vez al arrancar)
# ============================================================================

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


def seed_paises():
    """Rellena la tabla paises SOLO si está vacía (idempotente)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM paises")
        total = cursor.fetchone()[0]

        if total == 0:
            cursor.fast_executemany = True
            cursor.executemany(
                "INSERT INTO paises (pais_id, pais_nombre, pais_codigo) VALUES (?, ?, ?)",
                PAISES_SEED
            )
            conn.commit()
            print(f"[seed] Se insertaron {len(PAISES_SEED)} países.")
        else:
            print(f"[seed] La tabla paises ya tiene {total} registros. No se insertó nada.")
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# CONEXIÓN COMO DEPENDENCIA DE FASTAPI
# ============================================================================

def get_db():
    """
    Generador de conexiones a SQL Server.
    Se usa con Depends() en FastAPI para inyección de dependencias.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(cursor, row):
    """Convierte una fila (tupla) en un dict usando las columnas del cursor."""
    return {col[0]: value for col, value in zip(cursor.description, row)}


def rows_to_dicts(cursor, rows):
    """Convierte una lista de filas (tuplas) en una lista de dicts."""
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


# ============================================================================
# MODELOS PYDANTIC (Validación de datos de entrada)
# ============================================================================

class PersonaCreate(BaseModel):
    """Modelo para CREAR persona. Todos los campos son obligatorios."""
    nombre: str = Field(..., min_length=1, max_length=50)
    primer_apellido: str = Field(..., min_length=1, max_length=50)
    segundo_apellido: Optional[str] = Field(None, max_length=50)
    ci: str = Field(..., min_length=1, max_length=20)

    @field_validator('ci')
    @classmethod
    def ci_solo_numeros(cls, v):
        """Validación custom: CI debe ser solo dígitos."""
        if not re.match(r'^\d+$', v):
            raise ValueError('CI debe contener solo números')
        return v

    @field_validator('nombre', 'primer_apellido', 'segundo_apellido')
    @classmethod
    def solo_letras(cls, v):
        """Validación custom: nombres solo letras y espacios."""
        if v is not None and not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', v):
            raise ValueError('Solo se permiten letras y espacios')
        return v.strip() if v else v


class ViajeCreate(BaseModel):
    """Modelo para CREAR viaje. Requiere persona existente y país existente."""
    persona_id: int = Field(..., gt=0, description="ID de persona que viaja")
    pais_id: int = Field(..., gt=0, description="ID del país destino")
    fecha_llegada: date = Field(..., description="Fecha de llegada")

    @field_validator('fecha_llegada')
    @classmethod
    def no_futuro(cls, v):
        """Validación custom: no permitir fechas futuras."""
        if v > date.today():
            raise ValueError('La fecha no puede ser futura')
        return v


# ============================================================================
# APLICACIÓN FASTAPI
# ============================================================================

app = FastAPI(
    title="Python + SQL Server",
    description="Ejemplo mínimo para comprender la conexión a BD",
    version="1.0"
)


@app.on_event("startup")
def on_startup():
    """Crea la BD, las tablas y carga la semilla de países al arrancar."""
    init_db()
    seed_paises()


@app.get("/")
def root():
    """Endpoint de bienvenida. Lista qué puedes hacer."""
    return {
        "mensaje": "Tutorial Python + SQL Server",
        "endpoints": {
            "POST /by-paul/personas": "Crear persona",
            "GET /by-paul/personas": "Listar personas",
            "DELETE /by-paul/personas/{id}": "Eliminar persona + sus viajes",
            "POST /by-paul/viajes": "Crear viaje (necesita persona_id y pais_id)",
            "GET /by-paul/viajes": "Listar viajes"
        }
    }


# ============================================================================
# CRUD PERSONAS
# ============================================================================

@app.post("/by-paul/personas", status_code=201)
def crear_persona(persona: PersonaCreate, db=Depends(get_db)):
    """
    CREAR persona.

    En SQL Server usamos OUTPUT INSERTED.* para devolver la fila recién
    insertada en el mismo INSERT (no hace falta un SELECT aparte).

    Los ? son placeholders que pyodbc escapa automáticamente
    (previene SQL INJECTION).
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO personas (nombre, primer_apellido, segundo_apellido, ci)
            OUTPUT INSERTED.*
            VALUES (?, ?, ?, ?)
            """,
            (persona.nombre, persona.primer_apellido, persona.segundo_apellido, persona.ci)
        )
        row = cursor.fetchone()
        db.commit()
        return row_to_dict(cursor, row)
    except pyodbc.IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"CI {persona.ci} ya existe")
    finally:
        cursor.close()


@app.post("/by-paul/personas_ps", status_code=201)
def crear_persona_ps(persona: PersonaCreate, db=Depends(get_db)):
    """
    CREAR persona (variante que devuelve la fila por CI).
    Mantiene la misma lógica del tutorial original.
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO personas (nombre, primer_apellido, segundo_apellido, ci)
            VALUES (?, ?, ?, ?)
            """,
            (persona.nombre, persona.primer_apellido, persona.segundo_apellido, persona.ci)
        )
        db.commit()

        cursor.execute("SELECT * FROM personas WHERE ci = ?", (persona.ci,))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)
    except pyodbc.IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"CI {persona.ci} ya existe")
    finally:
        cursor.close()


@app.get("/by-paul/personas")
def listar_personas(db=Depends(get_db)):
    """LISTAR todas las personas."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM personas ORDER BY persona_id")
    resultados = rows_to_dicts(cursor, cursor.fetchall())
    cursor.close()
    return resultados


@app.delete("/by-paul/personas/{persona_id}")
def eliminar_persona(persona_id: int, db=Depends(get_db)):
    """
    ELIMINAR persona y TODOS sus viajes automáticamente.
    Gracias a ON DELETE CASCADE, SQL Server borra los viajes solos.
    """
    cursor = db.cursor()

    cursor.execute("SELECT * FROM personas WHERE persona_id = ?", (persona_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        raise HTTPException(status_code=404, detail="Persona no encontrada")
    persona = row_to_dict(cursor, row)

    cursor.execute("DELETE FROM personas WHERE persona_id = ?", (persona_id,))
    db.commit()
    cursor.close()

    return {
        "mensaje": "Persona eliminada",
        "persona": persona,
        "nota": "Sus viajes también fueron eliminados por CASCADE"
    }


# ============================================================================
# CRUD VIAJES
# ============================================================================

@app.post("/by-paul/viajes", status_code=201)
def crear_viaje(viaje: ViajeCreate, db=Depends(get_db)):
    """CREAR viaje. Verificamos que persona y país existen antes de insertar."""
    cursor = db.cursor()

    cursor.execute("SELECT persona_id FROM personas WHERE persona_id = ?", (viaje.persona_id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=404, detail="Persona no existe")

    cursor.execute("SELECT pais_id FROM paises WHERE pais_id = ?", (viaje.pais_id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=404, detail="País no existe")

    cursor.execute(
        """
        INSERT INTO viajes (persona_id, pais_id, fecha_llegada)
        OUTPUT INSERTED.*
        VALUES (?, ?, ?)
        """,
        (viaje.persona_id, viaje.pais_id, viaje.fecha_llegada)
    )
    row = cursor.fetchone()
    db.commit()
    nuevo_viaje = row_to_dict(cursor, row)
    cursor.close()

    return nuevo_viaje


@app.get("/by-paul/viajes")
def listar_viajes(db=Depends(get_db)):
    """LISTAR viajes con info de persona y país (JOIN)."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT
            v.viaje_id,
            v.fecha_llegada,
            p.nombre + ' ' + p.primer_apellido AS persona,
            pa.pais_nombre AS pais
        FROM viajes v
        JOIN personas p  ON v.persona_id = p.persona_id
        JOIN paises   pa ON v.pais_id    = pa.pais_id
        ORDER BY v.viaje_id
    """)
    resultados = rows_to_dicts(cursor, cursor.fetchall())
    cursor.close()
    return resultados
