"""
===========================================================================
Router de SETUP / inicialización
===========================================================================

Expone los "servicios" de preparación de la base de datos:

1. POST /setup/init-db        → crea la BD y las tablas base (si no existen).
2. POST /setup/seed-catalogos → carga departamentos y herramientas (estático).
3. POST /setup/seed-empleados → carga N empleados aleatorios (dinámico).

El orden recomendado es 1 → 2 → 3.
"""

from fastapi import APIRouter, Query

from ..database import init_db
from ..seeders import seed_catalogos, seed_empleados

router = APIRouter(prefix="/setup", tags=["1. Setup / Inicialización"])


@router.post("/init-db", summary="Crear la base de datos y las tablas base")
def endpoint_init_db():
    """
    Crea la base de datos `bd_herramientas` (si no existe) y todas las
    tablas base: `departamentos`, `empleados`, `herramientas` y `prestamos`.

    Es idempotente: llamarlo varias veces no rompe nada (las tablas ya
    creadas se ignoran gracias a `IF OBJECT_ID(...) IS NULL`).
    """
    init_db()
    return {
        "mensaje": "Base de datos y tablas base listas.",
        "tablas": ["departamentos", "empleados", "herramientas", "prestamos"],
        "nota": "Si ya existían, no se modificaron (idempotente).",
    }


@router.post("/seed-catalogos", summary="Cargar catálogos base (departamentos y herramientas)")
def endpoint_seed_catalogos():
    """
    Carga datos **estáticos** en las tablas `departamentos` y `herramientas`.

    Solo inserta si las tablas están vacías (idempotente), por lo que es
    seguro ejecutarlo varias veces.
    """
    resumen = seed_catalogos()
    return {
        "mensaje": "Seeder de catálogos ejecutado.",
        "detalle": resumen,
        "nota": "Solo inserta si las tablas estaban vacías.",
    }


@router.post("/seed-empleados", summary="Cargar N empleados (seeder dinámico)")
def endpoint_seed_empleados(
    cantidad: int = Query(
        10, ge=1, le=1000,
        description="Cantidad de empleados aleatorios a insertar.",
        examples=[20],
    )
):
    """
    Carga `cantidad` empleados **aleatorios** (nombre y puesto generados
    con Faker) repartidos entre los departamentos existentes.

    Requiere que ya existan departamentos (ejecuta antes
    `/setup/seed-catalogos`).
    """
    try:
        resumen = seed_empleados(cantidad)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "mensaje": f"Se insertaron {cantidad} empleados.",
        "detalle": resumen,
    }
