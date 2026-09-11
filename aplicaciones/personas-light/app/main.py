"""
===========================================================================
Python + SQLite con FastAPI
===========================================================================

Este archivo es INTENCIONALMENTE monolítico para que veas todo el flujo
de conexión a base de datos en un solo lugar.

FLUJO DE CONEXIÓN:
1. sqlite3 → Driver que viene incluido en Python (no se instala nada)
2. DATABASE_PATH → Ruta al archivo .db (la "base de datos" es un archivo)
3. get_db() → Función que crea y cierra conexiones
4. SQL directo → Queries crudos para ver exactamente qué se ejecuta

DIFERENCIAS CLAVE CON POSTGRESQL:
- SQLite no tiene servidor: la BD es un archivo en disco.
- Placeholders: ?  (en vez de %s de psycopg2).
- No soporta stored procedures (CALL). El endpoint /personas_ps usa
  INSERT inline para replicar la lógica del SP sp_crear_persona.
- Las foreign keys están DESACTIVADAS por defecto: hay que hacer
  PRAGMA foreign_keys = ON en cada conexión.
"""

import os
import sqlite3
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date
import re

# ============================================================================
# CONFIGURACIÓN DE CONEXIÓN
# ============================================================================
# sqlite3 es el "puente" entre Python y SQLite. Viene en la librería estándar.
# No necesita host, puerto, usuario ni password: solo la ruta al archivo .db.
# Si el archivo no existe, SQLite lo crea automáticamente al conectarse.

DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/personas.db")

# ============================================================================
# CREACIÓN DEL ESQUEMA (TABLAS)
# ============================================================================
# SQLite no crea las tablas por nosotros: las creamos aquí al arrancar.
# Conservamos las MISMAS tablas y campos que la versión PostgreSQL.

def init_db():
    """
    Crea las tablas si no existen. Se ejecuta una vez al iniciar la app.
    """
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
            FOREIGN KEY (persona_id) REFERENCES personas(persona_id) ON DELETE CASCADE,
            FOREIGN KEY (pais_id)    REFERENCES paises(pais_id)    ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_viajes_persona ON viajes(persona_id);
        CREATE INDEX IF NOT EXISTS idx_viajes_pais    ON viajes(pais_id);
    """)
    conn.commit()
    conn.close()


# ============================================================================
# SEMILLA DE PAÍSES (se ejecuta una sola vez al arrancar)
# ============================================================================
# Lista de países relevantes, con Bolivia primero (país de referencia del
# tutorial). Si la tabla ya tiene datos, NO se vuelve a insertar (es
# idempotente), así que reiniciar el contenedor no duplica nada.

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
    """
    Rellena la tabla paises SOLO si está vacía.
    Es idempotente: si ya hay países, no inserta nada.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM paises")
    total = cursor.fetchone()["total"]

    if total == 0:
        cursor.executemany(
            "INSERT INTO paises (pais_id, pais_nombre, pais_codigo) VALUES (?, ?, ?)",
            PAISES_SEED
        )
        conn.commit()
        print(f"[seed] Se insertaron {len(PAISES_SEED)} países (Bolivia primero).")
    else:
        print(f"[seed] La tabla paises ya tiene {total} registros. No se insertó nada.")

    cursor.close()
    conn.close()


# ============================================================================
# CONEXIÓN A LA BASE DE DATOS
# ============================================================================
# get_db() es un "generador" que:
#   1. Abre una conexión cuando alguien la necesita
#   2. La entrega para usarla
#   3. La cierra automáticamente cuando termina (incluso si hay error)
#
# sqlite3.Row permite acceder a las columnas por nombre: row['nombre']
# en vez de por índice: row[0]
#
# PRAGMA foreign_keys = ON es OBLIGATORIO en SQLite para que respete
# las FOREIGN KEY y el ON DELETE CASCADE. Sin esto, las FK son ignoradas.

def get_db():
    """
    Generador de conexiones a SQLite.
    Se usa con Depends() en FastAPI para inyección de dependencias.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


# ============================================================================
# MODELOS PYDANTIC (Validación de datos de entrada)
# ============================================================================
# Pydantic valida AUTOMÁTICAMENTE antes de que llegue a tu código.
# Si el usuario manda datos mal, FastAPI devuelve error 422 sin que hagas nada.

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
    title="Python + SQLite",
    description="Ejemplo mínimo para comprender la conexión a BD",
    version="1.0"
)


@app.on_event("startup")
def on_startup():
    """Crea las tablas y carga la semilla de países al arrancar."""
    init_db()
    seed_paises()


@app.get("/")
def root():
    """Endpoint de bienvenida. Lista qué puedes hacer."""
    return {
        "mensaje": "Tutorial Python + SQLite",
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

    En SQLite usamos INSERT + lastrowid + SELECT (en vez de RETURNING *)
    porque RETURNING deja el statement "en progreso" y bloquea el commit.

    ? son "placeholders" que sqlite3 escapa automáticamente.
    Esto previene SQL INJECTION.
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
        db.commit()  # ¡IMPORTANTE! Sin commit, los cambios no se guardan.
        persona_id = cursor.lastrowid
        cursor.execute("SELECT * FROM personas WHERE persona_id = ?", (persona_id,))
        return dict(cursor.fetchone())
    except sqlite3.IntegrityError:
        db.rollback()  # Si falla (CI duplicado), deshacemos todo.
        raise HTTPException(status_code=400, detail=f"CI {persona.ci} ya existe")
    finally:
        cursor.close()




@app.post("/by-paul/personas_ps", status_code=201)
def crear_persona_ps(persona: PersonaCreate, db=Depends(get_db)):
    """
    CREAR persona (variante "procedimiento almacenado").

    NOTA: SQLite NO soporta stored procedures (CALL).
    En la versión PostgreSQL esto llamaba a `sp_crear_persona`. Aquí
    replicamos la MISMA lógica con un INSERT inline, conservando el
    endpoint y su comportamiento.
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

        # Como el INSERT no retorna nada (sin RETURNING), hacemos SELECT
        cursor.execute(
            "SELECT * FROM personas WHERE ci = ?",
            (persona.ci,)
        )
        return dict(cursor.fetchone())

    except sqlite3.IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"CI {persona.ci} ya existe")
    finally:
        cursor.close()




@app.get("/by-paul/personas")
def listar_personas(db=Depends(get_db)):
    """
    LISTAR todas las personas.

    SQL: SELECT *  FROM personas
    """
    cursor = db.cursor()
    cursor.execute("SELECT *  FROM personas ORDER BY persona_id")
    resultados = [dict(r) for r in cursor.fetchall()]
    cursor.close()
    return resultados


@app.delete("/by-paul/personas/{persona_id}")
def eliminar_persona(persona_id: int, db=Depends(get_db)):
    """
    ELIMINAR persona y TODOS sus viajes automáticamente.

    Gracias a ON DELETE CASCADE en la foreign key de viajes.persona_id
    (y PRAGMA foreign_keys = ON), SQLite borra los viajes de esa persona
    automáticamente.

    SQL:
        DELETE FROM personas WHERE persona_id = ?
    """
    cursor = db.cursor()

    # Verificar que existe
    cursor.execute("SELECT * FROM personas WHERE persona_id = ?", (persona_id,))
    persona = cursor.fetchone()

    if not persona:
        cursor.close()
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    # Eliminar (los viajes se borran solos por CASCADE)
    cursor.execute("DELETE FROM personas WHERE persona_id = ?", (persona_id,))
    db.commit()
    cursor.close()

    return {
        "mensaje": "Persona eliminada",
        "persona": dict(persona),
        "nota": "Sus viajes también fueron eliminados por CASCADE"
    }


# ============================================================================
# CRUD VIAJES
# ============================================================================

@app.post("/by-paul/viajes", status_code=201)
def crear_viaje(viaje: ViajeCreate, db=Depends(get_db)):
    """
    CREAR viaje.

    Verificamos manualmente que persona_id y pais_id existen
    antes de insertar (integridad referencial).
    """
    cursor = db.cursor()

    # Verificar que la persona existe
    cursor.execute("SELECT persona_id FROM personas WHERE persona_id = ?", (viaje.persona_id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=404, detail="Persona no existe")

    # Verificar que el país existe
    cursor.execute("SELECT pais_id FROM paises WHERE pais_id = ?", (viaje.pais_id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=404, detail="País no existe")

    # Insertar viaje (usamos lastrowid en vez de RETURNING para evitar el
    # error "cannot commit transaction - SQL statements in progress")
    cursor.execute(
        """
        INSERT INTO viajes (persona_id, pais_id, fecha_llegada)
        VALUES (?, ?, ?)
        """,
        (viaje.persona_id, viaje.pais_id, viaje.fecha_llegada)
    )
    db.commit()
    viaje_id = cursor.lastrowid
    cursor.execute("SELECT * FROM viajes WHERE viaje_id = ?", (viaje_id,))
    nuevo_viaje = dict(cursor.fetchone())
    cursor.close()

    return nuevo_viaje


@app.get("/by-paul/viajes")
def listar_viajes(db=Depends(get_db)):
    """
    LISTAR viajes con info de persona y país (JOIN).

    SQL con JOIN para traer datos relacionados en una sola query.
    SQLite soporta || para concatenar strings, igual que PostgreSQL.
    """
    cursor = db.cursor()
    cursor.execute("""
        SELECT
            v.viaje_id,
            v.fecha_llegada,
            p.nombre || ' ' || p.primer_apellido as persona,
            pa.pais_nombre as pais
        FROM viajes v
        JOIN personas p ON v.persona_id = p.persona_id
        JOIN paises pa ON v.pais_id = pa.pais_id
        ORDER BY v.viaje_id
    """)
    resultados = [dict(r) for r in cursor.fetchall()]
    cursor.close()
    return resultados
