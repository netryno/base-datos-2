"""
===========================================================================
Control de Herramientas de una Empresa — FastAPI + SQL Server
===========================================================================

PROBLEMA
--------
Una empresa de construcción controla el uso de sus herramientas:
- Empleado: id, nombre, puesto. Pertenece a un único Departamento.
- Departamento: código y nombre. (1:N con empleados)
- Herramienta: código de inventario, nombre y estado
  (nuevo / usado / en reparación).
- Un empleado puede pedir prestadas varias herramientas a la vez; una
  herramienta solo puede estar prestada a un empleado a la vez (N:M
  resuelto con la tabla `prestamos` + índice único filtrado).

ARQUITECTURA (simple y organizada, ni monolito ni compleja)
-----------------------------------------------------------
app/
  config.py      → configuración de conexión (variables de entorno).
  database.py    → conexión, init_db(), get_db(), utilidades de filas.
  schemas.py     → modelos Pydantic (validación + Swagger).
  seeders.py     → catálogos estáticos + seeder dinámico de empleados.
  routers/
    setup.py         → 1) init-db  2) seed-catalogos  3) seed-empleados
    departamentos.py → CRUD departamento
    herramientas.py  → CRUD herramienta
    empleados.py     → CRUD empleado
    prestamos.py     → préstamo / devolución (relación N:M)
  main.py        → crea la app, arranca el esquema e incluye los routers.

FLUJO DE USO
-----------
1. (automático al arrancar) se crea la BD y las tablas.
2. POST /setup/seed-catalogos   → carga departamentos y herramientas.
3. POST /setup/seed-empleados?cantidad=20 → carga 20 empleados.
4. Usar los CRUD de cada entidad.
5. POST /prestamos para prestar herramientas a empleados.

Swagger:  http://localhost:8075/docs
"""

from fastapi import FastAPI

from .database import init_db
from .routers import setup, departamentos, herramientas, empleados, prestamos

app = FastAPI(
    title="Control de Herramientas — Python + SQL Server",
    description=(
        "API para gestionar el préstamo de herramientas de una empresa de "
        "construcción.\n\n"
        "**Modelo Entidad-Relación**\n\n"
        "```\n"
        "DEPARTAMENTO 1 ─── N EMPLEADO N ─── M HERRAMIENTA\n"
        "```\n\n"
        "- Un departamento tiene muchos empleados; un empleado pertenece a "
        "un solo departamento.\n"
        "- Un empleado puede pedir varias herramientas a la vez; una "
        "herramienta solo puede estar prestada a un empleado a la vez "
        "(índice único filtrado).\n\n"
        "**Pasos recomendados**\n"
        "1. `POST /setup/init-db` (se ejecuta solo al arrancar).\n"
        "2. `POST /setup/seed-catalogos`.\n"
        "3. `POST /setup/seed-empleados?cantidad=20`.\n"
        "4. `POST /setup/seed-prestamos?cantidad=5` (préstamos de ejemplo).\n"
        "5. Usar los CRUD de departamentos, herramientas y empleados.\n"
        "6. `POST /prestamos` para prestar/devolver herramientas.\n"
    ),
    version="2.0",
)


@app.on_event("startup")
def on_startup():
    """Crea la BD y las tablas base al arrancar (idempotente)."""
    init_db()


@app.get("/", tags=["0. Inicio"], summary="Bienvenida y mapa de endpoints")
def root():
    return {
        "proyecto": "Control de Herramientas — Python + SQL Server",
        "puerto": 8075,
        "swagger": "/docs",
        "modelo_er": "DEPARTAMENTO 1─N EMPLEADO N─M HERRAMIENTA",
        "pasos": [
            "POST /setup/init-db            (crea BD y tablas)",
            "POST /setup/seed-catalogos     (carga departamentos y herramientas)",
            "POST /setup/seed-empleados?cantidad=20  (carga 20 empleados)",
            "POST /setup/seed-prestamos?cantidad=5   (carga préstamos de ejemplo)",
            "CRUD /departamentos, /herramientas, /empleados",
            "POST /prestamos  →  prestar/devolver herramientas",
        ],
    }


# Incluir routers (cada uno con su prefijo y tags).
app.include_router(setup.router)
app.include_router(departamentos.router)
app.include_router(herramientas.router)
app.include_router(empleados.router)
app.include_router(prestamos.router)
