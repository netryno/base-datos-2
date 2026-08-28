"""
===========================================================================
Préstamos (relación N:M Empleado ↔ Herramienta)
===========================================================================

Este router es el "bonus" que demuestra cómo se materializa la relación
N:M del enunciado:

  "Un empleado puede solicitar prestadas varias herramientas a la vez,
   y una herramienta específica solo puede estar prestada a un empleado
   a la vez."

Esa regla se cumple en la BD con un ÍNDICE ÚNICO FILTRADO:
    CREATE UNIQUE INDEX ux_prestamos_herramienta_activa
        ON prestamos(herramienta_id)
        WHERE fecha_devolucion IS NULL

Operaciones:
- POST /prestamos                    → registrar un préstamo
- POST /prestamos/{prestamo_id}/devolver → devolver la herramienta
- GET  /prestamos                    → listar préstamos (con JOINs)
- GET  /prestamos/activos            → solo préstamos sin devolver
"""

import pyodbc
from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import get_db, fetch_one, fetch_all
from ..schemas import PrestamoCreate, DevolucionOut

router = APIRouter(prefix="/prestamos", tags=["5. Préstamos (N:M)"])


@router.post("", response_model=DevolucionOut, status_code=201,
             summary="Registrar un préstamo")
def prestar(body: PrestamoCreate, db=Depends(get_db)):
    """
    Presta una `herramienta` a un `empleado`.

    - Verifica que el empleado y la herramienta existan.
    - El índice único filtrado `ux_prestamos_herramienta_activa` garantiza
      que una herramienta no pueda estar prestada a dos empleados a la
      vez: si ya hay un préstamo abierto, SQL Server lanza un error de
      violación de índice único y devolvemos 409.
    - `fecha_prestamo` se rellena con GETDATE() por defecto.
    """
    cursor = db.cursor()
    try:
        # Validar empleado
        cursor.execute("SELECT 1 FROM empleados WHERE empleado_id = ?", (body.empleado_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "El empleado no existe.")
        # Validar herramienta
        cursor.execute("SELECT 1 FROM herramientas WHERE herramienta_id = ?", (body.herramienta_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "La herramienta no existe.")

        cursor.execute(
            """
            INSERT INTO prestamos (empleado_id, herramienta_id)
            OUTPUT INSERTED.*
            VALUES (?, ?)
            """,
            (body.empleado_id, body.herramienta_id),
        )
        nuevo = fetch_one(cursor)
        db.commit()
        return nuevo
    except pyodbc.IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "La herramienta ya está prestada. Devuélvela antes de prestarla de nuevo.",
        )
    finally:
        cursor.close()


@router.post("/{prestamo_id}/devolver", response_model=DevolucionOut,
             summary="Devolver una herramienta prestada")
def devolver(prestamo_id: int, db=Depends(get_db)):
    """
    Marca un préstamo como devuelto poniendo `fecha_devolucion = GETDATE()`.

    Al quedar `fecha_devolucion` con valor, el índice único filtrado deja
    de aplicar a esa herramienta, por lo que se puede volver a prestar.
    """
    cursor = db.cursor()
    try:
        # Verificar que exista y esté activo
        cursor.execute(
            "SELECT * FROM prestamos WHERE prestamo_id = ? AND fecha_devolucion IS NULL",
            (prestamo_id,),
        )
        if not cursor.fetchone():
            raise HTTPException(404, "Préstamo no encontrado o ya devuelto.")

        cursor.execute(
            """
            UPDATE prestamos
            SET fecha_devolucion = GETDATE()
            OUTPUT INSERTED.*
            WHERE prestamo_id = ?
            """,
            (prestamo_id,),
        )
        res = fetch_one(cursor)
        db.commit()
        return res
    finally:
        cursor.close()


@router.get("", summary="Listar préstamos (con JOINs)")
def listar(
    solo_activos: bool = Query(False, description="Si true, solo préstamos sin devolver."),
    db=Depends(get_db),
):
    """
    Lista los préstamos con el nombre del empleado, el departamento y la
    herramienta (tres JOIN). Muestra cómo se "navega" el modelo ER completo:

        prestamos → empleados → departamentos
                 → herramientas
    """
    cursor = db.cursor()
    sql = """
        SELECT  p.prestamo_id,
                p.empleado_id,
                e.empleado_nombre,
                d.departamento_nombre,
                p.herramienta_id,
                h.codigo_inventario,
                h.nombre AS herramienta_nombre,
                p.fecha_prestamo,
                p.fecha_devolucion,
                CASE WHEN p.fecha_devolucion IS NULL THEN 'activo'
                     ELSE 'devuelto' END AS estado
        FROM prestamos p
        JOIN empleados    e ON e.empleado_id    = p.empleado_id
        JOIN departamentos d ON d.departamento_id = e.departamento_id
        JOIN herramientas  h ON h.herramienta_id = p.herramienta_id
    """
    if solo_activos:
        sql += " WHERE p.fecha_devolucion IS NULL"
    sql += " ORDER BY p.prestamo_id"

    cursor.execute(sql)
    res = fetch_all(cursor)
    cursor.close()
    return res


@router.get("/activos", summary="Listar solo préstamos activos")
def activos(db=Depends(get_db)):
    """Atajo a `/prestamos?solo_activos=true`."""
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT  p.prestamo_id,
                p.empleado_id,
                e.empleado_nombre,
                d.departamento_nombre,
                p.herramienta_id,
                h.codigo_inventario,
                h.nombre AS herramienta_nombre,
                p.fecha_prestamo,
                p.fecha_devolucion,
                'activo' AS estado
        FROM prestamos p
        JOIN empleados    e ON e.empleado_id    = p.empleado_id
        JOIN departamentos d ON d.departamento_id = e.departamento_id
        JOIN herramientas  h ON h.herramienta_id = p.herramienta_id
        WHERE p.fecha_devolucion IS NULL
        ORDER BY p.prestamo_id
        """
    )
    res = fetch_all(cursor)
    cursor.close()
    return res
