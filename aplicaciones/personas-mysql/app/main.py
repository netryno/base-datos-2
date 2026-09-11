"""
===========================================================================
Python + MySQL con FastAPI
===========================================================================

Este archivo es INTENCIONALMENTE monolítico para que veas todo el flujo
de conexión a base de datos en un solo lugar.

FLUJO DE CONEXIÓN:
1. mysql.connector → Driver oficial de Oracle para hablar con MySQL.
2. Variables de entorno → HOST, PORT, USER, PASSWORD, DATABASE.
3. get_db() → Función que crea y cierra conexiones.
4. SQL directo → Queries crudos para ver exactamente qué se ejecuta.

DIFERENCIAS CLAVE CON SQLITE:
- MySQL SÍ tiene servidor: hay que indicar host, puerto, usuario y password.
- Placeholders: %s  (en vez de ? de sqlite3).
- Soporta stored procedures (CALL) con cursor.callproc(...).
- Las foreign keys están ACTIVADAS por defecto en el engine InnoDB:
  no hace que hacer ningún PRAGMA.
- AUTO_INCREMENT en vez de AUTOINCREMENT.
- Para obtener el id recién insertado usamos cursor.lastrowid.
"""

import os
import mysql.connector
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date
import re

# ============================================================================
# CONFIGURACIÓN DE CONEXIÓN
# ============================================================================
# mysql.connector es el driver oficial de Oracle para MySQL.
# A diferencia de SQLite, MySQL es un servidor: necesita host, puerto,
# usuario, password y nombre de la base de datos. Los leemos de variables
# de entorno (definidas en docker-compose.yml).

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
DB_NAME = os.getenv("DB_NAME", "personas_db")


def get_connection():
    """
    Crea y devuelve una conexión MySQL (sin cursor todavía).
    El modo "dictionary" (filas como dict) se activa al crear el cursor
    con cursor(dictionary=True), no en la conexión.
    """
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False,
    )


# ============================================================================
# CREACIÓN DEL ESQUEMA (TABLAS)
# ============================================================================
# MySQL no crea las tablas por nosotros: las creamos aquí al arrancar.
# Conservamos las MISMAS tablas y campos que la versión SQLite.
# Usamos ENGINE=InnoDB para que respete las FOREIGN KEY y el ON DELETE CASCADE.

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS paises (
        pais_id      INT PRIMARY KEY,
        pais_nombre  VARCHAR(50) NOT NULL,
        pais_codigo  VARCHAR(5)  NOT NULL
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE IF NOT EXISTS personas (
        persona_id       INT PRIMARY KEY AUTO_INCREMENT,
        nombre           VARCHAR(50) NOT NULL,
        primer_apellido  VARCHAR(50) NOT NULL,
        segundo_apellido VARCHAR(50),
        ci               VARCHAR(20) NOT NULL UNIQUE
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE IF NOT EXISTS viajes (
        viaje_id      INT PRIMARY KEY AUTO_INCREMENT,
        persona_id    INT NOT NULL,
        pais_id       INT NOT NULL,
        fecha_llegada DATE NOT NULL,
        FOREIGN KEY (persona_id) REFERENCES personas(persona_id) ON DELETE CASCADE,
        FOREIGN KEY (pais_id)    REFERENCES paises(pais_id)    ON DELETE CASCADE,
        INDEX idx_viajes_persona (persona_id),
        INDEX idx_viajes_pais    (pais_id)
    ) ENGINE=InnoDB
    """,
]


def init_db():
    """
    Crea las tablas si no existen. Se ejecuta una vez al iniciar la app.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
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
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT COUNT(*) AS total FROM paises")
        total = cursor.fetchone()["total"]

        if total == 0:
            cursor.executemany(
                "INSERT INTO paises (pais_id, pais_nombre, pais_codigo) VALUES (%s, %s, %s)",
                PAISES_SEED
            )
            conn.commit()
            print(f"[seed] Se insertaron {len(PAISES_SEED)} países (Bolivia primero).")
        else:
            print(f"[seed] La tabla paises ya tiene {total} registros. No se insertó nada.")
    finally:
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
# dictionary=True se pasa al crear cada cursor (cursor(dictionary=True))
# y permite acceder a las columnas por nombre: row['nombre'] en vez de
# por índice: row[0].
#
# En MySQL con InnoDB, las FOREIGN KEY y el ON DELETE CASCADE se respetan
# por defecto: no hace falta ningún PRAGMA como en SQLite.

def get_db():
    """
    Generador de conexiones a MySQL.
    Se usa con Depends() en FastAPI para inyección de dependencias.
    """
    conn = get_connection()
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
    title="Python + MySQL",
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
        "mensaje": "Tutorial Python + MySQL",
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

    En MySQL usamos INSERT + lastrowid + SELECT (en vez de RETURNING *)
    porque RETURNING no está soportado en todas las versiones de MySQL.

    %s son "placeholders" que mysql.connector escapa automáticamente.
    Esto previene SQL INJECTION.
    """
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            INSERT INTO personas (nombre, primer_apellido, segundo_apellido, ci)
            VALUES (%s, %s, %s, %s)
            """,
            (persona.nombre, persona.primer_apellido, persona.segundo_apellido, persona.ci)
        )
        db.commit()  # ¡IMPORTANTE! Sin commit, los cambios no se guardan.
        persona_id = cursor.lastrowid
        cursor.execute("SELECT * FROM personas WHERE persona_id = %s", (persona_id,))
        return cursor.fetchone()
    except mysql.connector.IntegrityError:
        db.rollback()  # Si falla (CI duplicado), deshacemos todo.
        raise HTTPException(status_code=400, detail=f"CI {persona.ci} ya existe")
    finally:
        cursor.close()




@app.post("/by-paul/personas_ps", status_code=201)
def crear_persona_ps(persona: PersonaCreate, db=Depends(get_db)):
    """
    CREAR persona (variante "procedimiento almacenado").

    MySQL SÍ soporta stored procedures (CALL). Aquí mantenemos la misma
    lógica con un INSERT inline para conservar el comportamiento del
    tutorial original; si tuvieras un SP `sp_crear_persona` podrías
    usar cursor.callproc('sp_crear_persona', (...)) en su lugar.
    """
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            INSERT INTO personas (nombre, primer_apellido, segundo_apellido, ci)
            VALUES (%s, %s, %s, %s)
            """,
            (persona.nombre, persona.primer_apellido, persona.segundo_apellido, persona.ci)
        )
        db.commit()

        # Como el INSERT no retorna nada, hacemos SELECT
        cursor.execute(
            "SELECT * FROM personas WHERE ci = %s",
            (persona.ci,)
        )
        return cursor.fetchone()

    except mysql.connector.IntegrityError:
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
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT *  FROM personas ORDER BY persona_id")
    resultados = cursor.fetchall()
    cursor.close()
    return resultados


@app.delete("/by-paul/personas/{persona_id}")
def eliminar_persona(persona_id: int, db=Depends(get_db)):
    """
    ELIMINAR persona y TODOS sus viajes automáticamente.

    Gracias a ON DELETE CASCADE en la foreign key de viajes.persona_id
    (y al engine InnoDB), MySQL borra los viajes de esa persona
    automáticamente.

    SQL:
        DELETE FROM personas WHERE persona_id = %s
    """
    cursor = db.cursor(dictionary=True)

    # Verificar que existe
    cursor.execute("SELECT * FROM personas WHERE persona_id = %s", (persona_id,))
    persona = cursor.fetchone()

    if not persona:
        cursor.close()
        raise HTTPException(status_code=404, detail="Persona no encontrada")

    # Eliminar (los viajes se borran solos por CASCADE)
    cursor.execute("DELETE FROM personas WHERE persona_id = %s", (persona_id,))
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
    """
    CREAR viaje.

    Verificamos manualmente que persona_id y pais_id existen
    antes de insertar (integridad referencial).
    """
    cursor = db.cursor(dictionary=True)

    # Verificar que la persona existe
    cursor.execute("SELECT persona_id FROM personas WHERE persona_id = %s", (viaje.persona_id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=404, detail="Persona no existe")

    # Verificar que el país existe
    cursor.execute("SELECT pais_id FROM paises WHERE pais_id = %s", (viaje.pais_id,))
    if not cursor.fetchone():
        cursor.close()
        raise HTTPException(status_code=404, detail="País no existe")

    # Insertar viaje (usamos lastrowid para obtener el id generado)
    cursor.execute(
        """
        INSERT INTO viajes (persona_id, pais_id, fecha_llegada)
        VALUES (%s, %s, %s)
        """,
        (viaje.persona_id, viaje.pais_id, viaje.fecha_llegada)
    )
    db.commit()
    viaje_id = cursor.lastrowid
    cursor.execute("SELECT * FROM viajes WHERE viaje_id = %s", (viaje_id,))
    nuevo_viaje = cursor.fetchone()
    cursor.close()

    return nuevo_viaje


@app.get("/by-paul/viajes")
def listar_viajes(db=Depends(get_db)):
    """
    LISTAR viajes con info de persona y país (JOIN).

    SQL con JOIN para traer datos relacionados en una sola query.
    MySQL soporta CONCAT() para concatenar strings (|| no es estándar).
    """
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            v.viaje_id,
            v.fecha_llegada,
            CONCAT(p.nombre, ' ', p.primer_apellido) as persona,
            pa.pais_nombre as pais
        FROM viajes v
        JOIN personas p ON v.persona_id = p.persona_id
        JOIN paises pa ON v.pais_id = pa.pais_id
        ORDER BY v.viaje_id
    """)
    resultados = cursor.fetchall()
    cursor.close()
    return resultados
