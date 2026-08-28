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
