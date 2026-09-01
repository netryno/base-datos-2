"""
===========================================================================
Seeders (carga de datos iniciales)
===========================================================================

Dos tipos de seeder:
- seed_catalogos():  ESTÁTICO. Inserta departamentos y herramientas fijos,
                     solo si las tablas están vacías (idempotente).
- seed_empleados(n): DINÁMICO. Genera `n` empleados con Faker y los reparte
                     entre los departamentos existentes.

Ambos son idempotentes: llamarlos varias veces no duplica datos (los
catálogos) o simplemente añade más (los empleados).
"""

import random
from faker import Faker

from .database import get_connection

faker = Faker("es_ES")


# ---------------------------------------------------------------------------
# Datos estáticos de catálogos
# ---------------------------------------------------------------------------

DEPARTAMENTOS_SEED = [
    ("CAR", "Carpintería"),
    ("PLO", "Plomería"),
    ("ELE", "Electricidad"),
    ("ALB", "Albañilería"),
    ("PIN", "Pintura"),
    ("JAR", "Jardinería"),
    ("SOL", "Soldadura"),
    ("MEC", "Mecánica"),
]

HERRAMIENTAS_SEED = [
    ("HERR-001", "Taladro percutor",        "nuevo"),
    ("HERR-002", "Sierra circular",         "usado"),
    ("HERR-003", "Amoladora angular",       "usado"),
    ("HERR-004", "Destornillador eléctrico","nuevo"),
    ("HERR-005", "Martillo rompedor",       "en reparacion"),
    ("HERR-006", "Lijadora orbital",        "usado"),
    ("HERR-007", "Sierra de calar",         "nuevo"),
    ("HERR-008", "Compresor de aire",       "usado"),
    ("HERR-009", "Soldadora inverter",      "en reparacion"),
    ("HERR-010", "Nivel láser",             "nuevo"),
    ("HERR-011", "Andamio metálico",        "usado"),
    ("HERR-012", "Carretilla de obra",      "usado"),
    ("HERR-013", "Mezcladora de cemento",   "en reparacion"),
    ("HERR-014", "Pistola de pintura",      "nuevo"),
    ("HERR-015", "Hidrolavadora",           "usado"),
]

# Puestos coherentes con los departamentos, para el seeder dinámico.
PUESTOS = [
    "Operario", "Oficial", "Ayudante", "Capataz", "Especialista", "Técnico"
]


# ---------------------------------------------------------------------------
# Seeder estático: catálogos
# ---------------------------------------------------------------------------

def seed_catalogos() -> dict:
    """
    Inserta departamentos y herramientas SOLO si sus tablas están vacías.

    Devuelve un resumen con cuántos registros insertó.
    """
    conn = get_connection()
    cursor = conn.cursor()
    resumen = {"departamentos_insertados": 0, "herramientas_insertadas": 0}
    try:
        # Departamentos
        cursor.execute("SELECT COUNT(*) FROM departamentos")
        if cursor.fetchone()[0] == 0:
            cursor.fast_executemany = True
            cursor.executemany(
                "INSERT INTO departamentos (departamento_codigo, departamento_nombre) VALUES (?, ?)",
                DEPARTAMENTOS_SEED,
            )
            resumen["departamentos_insertados"] = len(DEPARTAMENTOS_SEED)

        # Herramientas
        cursor.execute("SELECT COUNT(*) FROM herramientas")
        if cursor.fetchone()[0] == 0:
            cursor.fast_executemany = True
            cursor.executemany(
                "INSERT INTO herramientas (codigo_inventario, nombre, estado) VALUES (?, ?, ?)",
                HERRAMIENTAS_SEED,
            )
            resumen["herramientas_insertadas"] = len(HERRAMIENTAS_SEED)

        conn.commit()
        return resumen
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------------------------
# Seeder dinámico: empleados
# ---------------------------------------------------------------------------

def seed_empleados(cantidad: int) -> dict:
    """
    Genera `cantidad` empleados aleatorios y los reparte entre los
    departamentos existentes. Requiere que existan departamentos.

    Devuelve un resumen con cuántos insertó y a qué departamentos.
    """
    if cantidad < 1:
        raise ValueError("La cantidad debe ser mayor o igual a 1.")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Necesitamos los IDs de departamentos existentes.
        cursor.execute("SELECT departamento_id FROM departamentos ORDER BY departamento_id")
        dept_ids = [r[0] for r in cursor.fetchall()]
        if not dept_ids:
            raise ValueError(
                "No hay departamentos. Ejecuta primero el seeder de catálogos."
            )

        filas = []
        for _ in range(cantidad):
            nombre = faker.name()
            puesto = random.choice(PUESTOS)
            dept = random.choice(dept_ids)
            filas.append((nombre, puesto, dept))

        cursor.fast_executemany = True
        cursor.executemany(
            "INSERT INTO empleados (empleado_nombre, puesto, departamento_id) VALUES (?, ?, ?)",
            filas,
        )
        conn.commit()
        return {
            "empleados_insertados": cantidad,
            "departamentos_disponibles": len(dept_ids),
        }
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------------------------
# Seeder dinámico: préstamos (relación N:M)
# ---------------------------------------------------------------------------

def seed_prestamos(cantidad_activos: int = 5) -> dict:
    """
    Crea préstamos aleatorios entre empleados y herramientas existentes.

    - Crea hasta `cantidad_activos` préstamos **activos** (sin devolver),
      uno por herramienta disponible (respeta el índice único filtrado:
      una herramienta, un solo préstamo activo a la vez).
    - Además crea algunos préstamos **históricos** (ya devueltos) para que
      se vea la relación N:M a lo largo del tiempo: una misma herramienta
      puede pasar por varios empleados en distintos momentos.

    Requiere que existan empleados y herramientas.

    Devuelve un resumen con cuántos préstamos activos e históricos creó.
    """
    if cantidad_activos < 0:
        raise ValueError("La cantidad no puede ser negativa.")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Empleados disponibles
        cursor.execute("SELECT empleado_id FROM empleados ORDER BY empleado_id")
        emp_ids = [r[0] for r in cursor.fetchall()]
        if not emp_ids:
            raise ValueError(
                "No hay empleados. Ejecuta primero /setup/seed-empleados."
            )

        # Herramientas disponibles (sin préstamo activo)
        cursor.execute(
            """
            SELECT h.herramienta_id
            FROM herramientas h
            WHERE NOT EXISTS (
                SELECT 1 FROM prestamos p
                WHERE p.herramienta_id = h.herramienta_id
                  AND p.fecha_devolucion IS NULL
            )
            ORDER BY h.herramienta_id
            """
        )
        disponibles = [r[0] for r in cursor.fetchall()]

        # Todas las herramientas (para préstamos históricos, sin restricción)
        cursor.execute("SELECT herramienta_id FROM herramientas ORDER BY herramienta_id")
        todas_herr = [r[0] for r in cursor.fetchall()]
        if not todas_herr:
            raise ValueError(
                "No hay herramientas. Ejecuta primero /setup/seed-catalogos."
            )

        # --- Préstamos activos: uno por herramienta disponible ----------
        random.shuffle(disponibles)
        activos_creados = min(cantidad_activos, len(disponibles))
        for i in range(activos_creados):
            cursor.execute(
                """
                INSERT INTO prestamos (empleado_id, herramienta_id)
                VALUES (?, ?)
                """,
                (random.choice(emp_ids), disponibles[i]),
            )

        # --- Préstamos históricos (ya devueltos) -----------------------
        # No chocan con el índice único filtrado (fecha_devolucion != NULL),
        # así que una misma herramienta puede tener varios a lo largo del
        # tiempo → demuestra el lado M de la relación N:M.
        historicos = min(5, len(todas_herr))
        for _ in range(historicos):
            dias = random.randint(1, 30)
            cursor.execute(
                """
                INSERT INTO prestamos (empleado_id, herramienta_id,
                                        fecha_prestamo, fecha_devolucion)
                VALUES (?, ?, DATEADD(day, -?, GETDATE()),
                        DATEADD(day, -?, GETDATE()))
                """,
                (random.choice(emp_ids), random.choice(todas_herr),
                 dias + 1, dias),
            )

        conn.commit()
        return {
            "prestamos_activos_creados": activos_creados,
            "prestamos_historicos_creados": historicos,
            "herramientas_disponibles": len(disponibles),
            "activos_solicitados": cantidad_activos,
            "nota": ("Si se crearon menos activos de los solicitados es porque "
                     "no había suficientes herramientas disponibles."),
        }
    finally:
        cursor.close()
        conn.close()
