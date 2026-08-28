"""
===========================================================================
Capa de acceso a datos (SQL Server)
===========================================================================

Aquí vive TODO lo relacionado con la conexión y la creación del esquema:
- get_connection()  → abre una conexión pyodbc.
- init_db()         → crea la BD (si no existe) y las tablas base.
- get_db()          → dependencia de FastAPI que entrega una conexión por
                      petición y la cierra al terminar.
- row_to_dict()     → utilidades para convertir filas en dicts.

DIFERENCIAS CLAVE DE SQL SERVER (vs MySQL):
- No existe CREATE TABLE IF NOT EXISTS → usamos IF OBJECT_ID(...) IS NULL.
- Placeholders: ?  (en vez de %s de MySQL).
- AUTO_INCREMENT → IDENTITY(1,1).
- lastrowid no es confiable → usamos OUTPUT INSERTED.* para devolver la fila.
- ENGINE=InnoDB no existe (las FK siempre se respetan).
- Índice único FILTRADO para "una herramienta prestada a un solo empleado
  a la vez" (WHERE fecha_devolucion IS NULL).
"""

import pyodbc
from .config import conn_str, DB_NAME


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

def get_connection(database: str = DB_NAME):
    """Crea y devuelve una conexión a SQL Server (transaccional)."""
    return pyodbc.connect(conn_str(database), autocommit=False)


# ---------------------------------------------------------------------------
# Esquema: sentencias DDL que crean las tablas si no existen
# ---------------------------------------------------------------------------
# Modelo Entidad-Relación del problema:
#
#   DEPARTAMENTO 1 ─── N EMPLEADO N ─── M HERRAMIENTA
#
#   - Un departamento tiene muchos empleados; un empleado pertenece a un
#     solo departamento (FK en empleados → departamentos).
#   - Un empleado puede pedir prestadas varias herramientas a la vez, y
#     una herramienta solo puede estar prestada a un empleado a la vez.
#     Esa relación N:M se resuelve con la tabla PRESTAMOS, y la regla de
#     "una herramienta prestada a un solo empleado" se cumple con un
#     ÍNDICE ÚNICO FILTRADO sobre (herramienta_id) WHERE fecha_devolucion
#     IS NULL: solo puede existir UN préstamo abierto por herramienta.
# ---------------------------------------------------------------------------

SCHEMA_STATEMENTS = [
    # --- departamentos ---------------------------------------------------
    """
    IF OBJECT_ID('dbo.departamentos', 'U') IS NULL
    CREATE TABLE departamentos (
        departamento_id     INT IDENTITY(1,1) PRIMARY KEY,
        departamento_codigo VARCHAR(10) NOT NULL UNIQUE,
        departamento_nombre VARCHAR(50) NOT NULL
    )
    """,
    # --- empleados --------------------------------------------------------
    """
    IF OBJECT_ID('dbo.empleados', 'U') IS NULL
    CREATE TABLE empleados (
        empleado_id     INT IDENTITY(1,1) PRIMARY KEY,
        empleado_nombre VARCHAR(60) NOT NULL,
        puesto          VARCHAR(50) NOT NULL,
        departamento_id INT NOT NULL,
        FOREIGN KEY (departamento_id) REFERENCES departamentos(departamento_id)
    )
    """,
    # --- herramientas -----------------------------------------------------
    """
    IF OBJECT_ID('dbo.herramientas', 'U') IS NULL
    CREATE TABLE herramientas (
        herramienta_id   INT IDENTITY(1,1) PRIMARY KEY,
        codigo_inventario VARCHAR(20) NOT NULL UNIQUE,
        nombre           VARCHAR(50) NOT NULL,
        estado           VARCHAR(20) NOT NULL
                         CHECK (estado IN ('nuevo','usado','en reparacion'))
    )
    """,
    # --- prestamos (tabla puente N:M) ------------------------------------
    """
    IF OBJECT_ID('dbo.prestamos', 'U') IS NULL
    CREATE TABLE prestamos (
        prestamo_id      INT IDENTITY(1,1) PRIMARY KEY,
        empleado_id      INT NOT NULL,
        herramienta_id   INT NOT NULL,
        fecha_prestamo   DATETIME NOT NULL DEFAULT GETDATE(),
        fecha_devolucion DATETIME NULL,
        FOREIGN KEY (empleado_id)    REFERENCES empleados(empleado_id),
        FOREIGN KEY (herramienta_id) REFERENCES herramientas(herramienta_id)
    )
    """,
    # --- índice único FILTRADO: una herramienta, un solo préstamo abierto -
    """
    IF NOT EXISTS (
        SELECT 1 FROM sys.indexes
        WHERE name = 'ux_prestamos_herramienta_activa'
          AND object_id = OBJECT_ID('dbo.prestamos')
    )
    CREATE UNIQUE INDEX ux_prestamos_herramienta_activa
        ON prestamos(herramienta_id)
        WHERE fecha_devolucion IS NULL
    """,
    # --- índices de apoyo para los JOIN más frecuentes --------------------
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_empleados_departamento')
    CREATE INDEX idx_empleados_departamento ON empleados(departamento_id)
    """,
]


def init_db():
    """
    Crea la base de datos (si no existe) y luego las tablas base.

    Se ejecuta automáticamente al arrancar la app (startup) y también se
    puede invocar manualmente vía POST /setup/init-db.
    """
    # 1. Conectar a 'master' con autocommit para poder ejecutar CREATE DATABASE.
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


# ---------------------------------------------------------------------------
# Dependencia de FastAPI
# ---------------------------------------------------------------------------

def get_db():
    """
    Generador de conexiones a SQL Server.

    Se usa con Depends() en FastAPI: abre una conexión por petición y la
    cierra automáticamente al terminar (haya o no error).
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
# Estas funciones combinan fetch + conversión a dict EN UN SOLO PASO, por lo
# que capturan `cursor.description` en el momento justo (antes de cualquier
# cursor.close()). Así se evita el error 'cursor has no attribute description'
# que aparece si se cierra el cursor antes de leer las columnas.

def fetch_one(cursor):
    """Devuelve la siguiente fila como dict, o None si no hay más filas."""
    row = cursor.fetchone()
    if row is None:
        return None
    cols = [c[0] for c in cursor.description]
    return dict(zip(cols, row))


def fetch_all(cursor):
    """Devuelve todas las filas restantes como una lista de dicts."""
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, r)) for r in cursor.fetchall()]


def row_to_dict(cursor, row):
    """Convierte una fila (tupla) en un dict usando las columnas del cursor."""
    return {col[0]: value for col, value in zip(cursor.description, row)}


def rows_to_dicts(cursor, rows):
    """Convierte una lista de filas (tuplas) en una lista de dicts."""
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, r)) for r in rows]
