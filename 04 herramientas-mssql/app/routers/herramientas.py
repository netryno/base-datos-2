"""
===========================================================================
CRUD de Herramientas
===========================================================================

Operaciones:
- POST   /herramientas          → crear
- GET    /herramientas          → listar (todas, con info de préstamo activo)
- GET    /herramientas/{id}     → obtener una
- PUT    /herramientas/{id}     → actualizar
- DELETE /herramientas/{id}     → eliminar (si no tiene préstamos)
"""

import pyodbc
from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_db, fetch_one, fetch_all
from ..schemas import HerramientaCreate, HerramientaUpdate, HerramientaOut

router = APIRouter(prefix="/herramientas", tags=["3. Herramientas"])


@router.post("", response_model=HerramientaOut, status_code=201,
             summary="Crear herramienta")
def crear(body: HerramientaCreate, db=Depends(get_db)):
    """
    Crea una nueva herramienta.

    El `estado` se valida con un CHECK en la BD ('nuevo', 'usado',
    'en reparacion'); si llega otro valor, SQL Server rechaza la inserción.
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO herramientas (codigo_inventario, nombre, estado)
            OUTPUT INSERTED.*
            VALUES (?, ?, ?)
            """,
            (body.codigo_inventario, body.nombre, body.estado),
        )
        nuevo = fetch_one(cursor)
        db.commit()
        return nuevo
    except pyodbc.IntegrityError:
        db.rollback()
        raise HTTPException(400, f"El código '{body.codigo_inventario}' ya existe.")
    except pyodbc.DataError:
        db.rollback()
        raise HTTPException(400, "Estado inválido. Use: nuevo, usado, en reparacion.")
    finally:
        cursor.close()


@router.get("", summary="Listar herramientas (con préstamo activo)")
def listar(
    solo_disponibles: bool = Query(
        False, description="Si true, devuelve solo las herramientas NO prestadas."
    ),
    db=Depends(get_db),
):
    """
    Lista las herramientas. Para cada una indica si está **prestada
    actualmente** (LEFT JOIN a `prestamos` donde `fecha_devolucion IS NULL`).

    Útil para ver la relación N:M en acción: una herramienta prestada
    muestra el empleado que la tiene.
    """
    cursor = db.cursor()
    sql = """
        SELECT  h.herramienta_id,
                h.codigo_inventario,
                h.nombre,
                h.estado,
                CASE
                    WHEN p.prestamo_id IS NOT NULL THEN 'prestada'
                    ELSE 'disponible'
                END AS estado_prestamo,
                p.prestamo_id,
                p.empleado_id,
                e.empleado_nombre
        FROM herramientas h
        LEFT JOIN prestamos p
               ON p.herramienta_id = h.herramienta_id
              AND p.fecha_devolucion IS NULL
        LEFT JOIN empleados  e ON e.empleado_id = p.empleado_id
    """
    if solo_disponibles:
        sql += " WHERE p.prestamo_id IS NULL"
    sql += " ORDER BY h.herramienta_id"

    cursor.execute(sql)
    res = fetch_all(cursor)
    cursor.close()
    return res


@router.get("/{herramienta_id}", response_model=HerramientaOut,
            summary="Obtener una herramienta")
def obtener(herramienta_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM herramientas WHERE herramienta_id = ?",
        (herramienta_id,),
    )
    res = fetch_one(cursor)
    cursor.close()
    if not res:
        raise HTTPException(404, "Herramienta no encontrada.")
    return res


@router.put("/{herramienta_id}", response_model=HerramientaOut,
            summary="Actualizar herramienta")
def actualizar(herramienta_id: int, body: HerramientaUpdate, db=Depends(get_db)):
    cursor = db.cursor()
    try:
        campos, valores = [], []
        for k, v in body.model_dump(exclude_unset=True).items():
            campos.append(f"{k} = ?")
            valores.append(v)
        if not campos:
            raise HTTPException(400, "No se envió ningún campo a actualizar.")

        valores.append(herramienta_id)
        cursor.execute(
            "UPDATE herramientas SET " + ", ".join(campos) +
            " OUTPUT INSERTED.* WHERE herramienta_id = ?",
            valores,
        )
        res = fetch_one(cursor)
        db.commit()
        if not res:
            raise HTTPException(404, "Herramienta no encontrada.")
        return res
    except pyodbc.IntegrityError:
        db.rollback()
        raise HTTPException(400, "El código indicado ya existe.")
    except pyodbc.DataError:
        db.rollback()
        raise HTTPException(400, "Estado inválido. Use: nuevo, usado, en reparacion.")
    finally:
        cursor.close()


@router.delete("/{herramienta_id}", summary="Eliminar herramienta")
def eliminar(herramienta_id: int, db=Depends(get_db)):
    """
    Elimina una herramienta. No se permite si tiene **préstamos**
    (la FK lo impide), para no perder el historial.
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            "SELECT * FROM herramientas WHERE herramienta_id = ?",
            (herramienta_id,),
        )
        herr = fetch_one(cursor)
        if not herr:
            raise HTTPException(404, "Herramienta no encontrada.")

        cursor.execute(
            "DELETE FROM herramientas WHERE herramienta_id = ?",
            (herramienta_id,),
        )
        db.commit()
        return {"mensaje": "Herramienta eliminada.", "herramienta": herr}
    except pyodbc.IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "No se puede eliminar: la herramienta tiene préstamos registrados.",
        )
    finally:
        cursor.close()
