"""
===========================================================================
CRUD de Empleados
===========================================================================

Operaciones:
- POST   /empleados          → crear
- GET    /empleados          → listar (con nombre de departamento)
- GET    /empleados/{id}     → obtener uno (con sus herramientas prestadas)
- PUT    /empleados/{id}     → actualizar
- DELETE /empleados/{id}     → eliminar (si no tiene préstamos)
"""

import pyodbc
from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db, fetch_one, fetch_all
from ..schemas import EmpleadoCreate, EmpleadoUpdate, EmpleadoOut

router = APIRouter(prefix="/empleados", tags=["4. Empleados"])


@router.post("", response_model=EmpleadoOut, status_code=201,
             summary="Crear empleado")
def crear(body: EmpleadoCreate, db=Depends(get_db)):
    """
    Crea un empleado. Verifica primero que el `departamento_id` exista
    (si no, 404) — esto demuestra la dependencia Empleado→Departamento.
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM departamentos WHERE departamento_id = ?",
            (body.departamento_id,),
        )
        if not cursor.fetchone():
            raise HTTPException(404, "El departamento indicado no existe.")

        cursor.execute(
            """
            INSERT INTO empleados (empleado_nombre, puesto, departamento_id)
            OUTPUT INSERTED.*
            VALUES (?, ?, ?)
            """,
            (body.empleado_nombre, body.puesto, body.departamento_id),
        )
        nuevo = fetch_one(cursor)
        db.commit()
        return nuevo
    finally:
        cursor.close()


@router.get("", summary="Listar empleados (con su departamento)")
def listar(db=Depends(get_db)):
    """
    Lista los empleados con el nombre de su departamento (INNER JOIN),
    demostrando la relación 1:N Departamento→Empleado.
    """
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT e.empleado_id, e.empleado_nombre, e.puesto,
               e.departamento_id, d.departamento_nombre
        FROM empleados e
        JOIN departamentos d ON d.departamento_id = e.departamento_id
        ORDER BY e.empleado_id
        """
    )
    res = fetch_all(cursor)
    cursor.close()
    return res


@router.get("/{empleado_id}", summary="Obtener un empleado (con herramientas prestadas)")
def obtener(empleado_id: int, db=Depends(get_db)):
    """
    Devuelve un empleado y las herramientas que tiene **prestadas ahora**
    (JOIN con `prestamos` + `herramientas` donde `fecha_devolucion IS NULL`).

    Muestra la relación N:M Empleado↔Herramienta.
    """
    cursor = db.cursor()
    # Datos del empleado + departamento
    cursor.execute(
        """
        SELECT e.empleado_id, e.empleado_nombre, e.puesto,
               e.departamento_id, d.departamento_nombre
        FROM empleados e
        JOIN departamentos d ON d.departamento_id = e.departamento_id
        WHERE e.empleado_id = ?
        """,
        (empleado_id,),
    )
    empleado = fetch_one(cursor)
    if not empleado:
        cursor.close()
        raise HTTPException(404, "Empleado no encontrado.")

    # Herramientas prestadas actualmente
    cursor.execute(
        """
        SELECT p.prestamo_id, h.herramienta_id, h.codigo_inventario,
               h.nombre, h.estado, p.fecha_prestamo
        FROM prestamos p
        JOIN herramientas h ON h.herramienta_id = p.herramienta_id
        WHERE p.empleado_id = ? AND p.fecha_devolucion IS NULL
        """,
        (empleado_id,),
    )
    empleado["herramientas_prestadas"] = fetch_all(cursor)
    cursor.close()
    return empleado


@router.put("/{empleado_id}", response_model=EmpleadoOut,
            summary="Actualizar empleado")
def actualizar(empleado_id: int, body: EmpleadoUpdate, db=Depends(get_db)):
    cursor = db.cursor()
    try:
        campos, valores = [], []
        for k, v in body.model_dump(exclude_unset=True).items():
            campos.append(f"{k} = ?")
            valores.append(v)
        if not campos:
            raise HTTPException(400, "No se envió ningún campo a actualizar.")

        # Si cambia de departamento, validar que exista.
        if "departamento_id" in body.model_dump(exclude_unset=True):
            cursor.execute(
                "SELECT 1 FROM departamentos WHERE departamento_id = ?",
                (body.departamento_id,),
            )
            if not cursor.fetchone():
                raise HTTPException(404, "El departamento indicado no existe.")

        valores.append(empleado_id)
        cursor.execute(
            "UPDATE empleados SET " + ", ".join(campos) +
            " OUTPUT INSERTED.* WHERE empleado_id = ?",
            valores,
        )
        res = fetch_one(cursor)
        db.commit()
        if not res:
            raise HTTPException(404, "Empleado no encontrado.")
        return res
    finally:
        cursor.close()


@router.delete("/{empleado_id}", summary="Eliminar empleado")
def eliminar(empleado_id: int, db=Depends(get_db)):
    """
    Elimina un empleado. No se permite si tiene **préstamos activos**
    (la FK lo impide).
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            "SELECT * FROM empleados WHERE empleado_id = ?",
            (empleado_id,),
        )
        emp = fetch_one(cursor)
        if not emp:
            raise HTTPException(404, "Empleado no encontrado.")

        cursor.execute("DELETE FROM empleados WHERE empleado_id = ?", (empleado_id,))
        db.commit()
        return {"mensaje": "Empleado eliminado.", "empleado": emp}
    except pyodbc.IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "No se puede eliminar: el empleado tiene préstamos registrados.",
        )
    finally:
        cursor.close()
