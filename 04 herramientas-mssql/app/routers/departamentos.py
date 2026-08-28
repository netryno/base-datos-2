"""
===========================================================================
CRUD de Departamentos
===========================================================================

Operaciones:
- POST   /departamentos          → crear
- GET    /departamentos          → listar (todos)
- GET    /departamentos/{id}     → obtener uno (con conteo de empleados)
- PUT    /departamentos/{id}     → actualizar
- DELETE /departamentos/{id}     → eliminar (si no tiene empleados)
"""

import pyodbc
from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db, fetch_one, fetch_all
from ..schemas import DepartamentoCreate, DepartamentoUpdate, DepartamentoOut

router = APIRouter(prefix="/departamentos", tags=["2. Departamentos"])


@router.post("", response_model=DepartamentoOut, status_code=201,
             summary="Crear departamento")
def crear(body: DepartamentoCreate, db=Depends(get_db)):
    """
    Crea un nuevo departamento.

    `OUTPUT INSERTED.*` devuelve la fila recién insertada en el mismo
    INSERT (no hace falta un SELECT aparte). Los `?` son placeholders
    que pyodbc escapa automáticamente (previene SQL injection).
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO departamentos (departamento_codigo, departamento_nombre)
            OUTPUT INSERTED.*
            VALUES (?, ?)
            """,
            (body.departamento_codigo, body.departamento_nombre),
        )
        nuevo = fetch_one(cursor)
        db.commit()
        return nuevo
    except pyodbc.IntegrityError:
        db.rollback()
        raise HTTPException(400, f"El código '{body.departamento_codigo}' ya existe.")
    finally:
        cursor.close()


@router.get("", response_model=list[DepartamentoOut],
             summary="Listar departamentos")
def listar(db=Depends(get_db)):
    """Lista todos los departamentos ordenados por id."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM departamentos ORDER BY departamento_id")
    res = fetch_all(cursor)
    cursor.close()
    return res


@router.get("/{departamento_id}", summary="Obtener un departamento (con # empleados)")
def obtener(departamento_id: int, db=Depends(get_db)):
    """
    Devuelve un departamento y cuántos empleados tiene (LEFT JOIN +
    COUNT). Si no existe, 404.
    """
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT d.departamento_id, d.departamento_codigo, d.departamento_nombre,
               COUNT(e.empleado_id) AS total_empleados
        FROM departamentos d
        LEFT JOIN empleados e ON e.departamento_id = d.departamento_id
        WHERE d.departamento_id = ?
        GROUP BY d.departamento_id, d.departamento_codigo, d.departamento_nombre
        """,
        (departamento_id,),
    )
    res = fetch_one(cursor)
    cursor.close()
    if not res:
        raise HTTPException(404, "Departamento no encontrado.")
    return res


@router.put("/{departamento_id}", response_model=DepartamentoOut,
            summary="Actualizar departamento")
def actualizar(departamento_id: int, body: DepartamentoUpdate, db=Depends(get_db)):
    """
    Actualiza los campos enviados (parcial). Usa `OUTPUT INSERTED.*` para
    devolver el resultado tras el UPDATE.
    """
    cursor = db.cursor()
    try:
        # Construir SET dinámico solo con los campos recibidos.
        campos, valores = [], []
        for k, v in body.model_dump(exclude_unset=True).items():
            campos.append(f"{k} = ?")
            valores.append(v)
        if not campos:
            raise HTTPException(400, "No se envió ningún campo a actualizar.")

        valores.append(departamento_id)
        cursor.execute(
            "UPDATE departamentos SET " + ", ".join(campos) +
            " OUTPUT INSERTED.* WHERE departamento_id = ?",
            valores,
        )
        res = fetch_one(cursor)
        db.commit()
        if not res:
            raise HTTPException(404, "Departamento no encontrado.")
        return res
    except pyodbc.IntegrityError:
        db.rollback()
        raise HTTPException(400, "El código indicado ya existe.")
    finally:
        cursor.close()


@router.delete("/{departamento_id}", summary="Eliminar departamento")
def eliminar(departamento_id: int, db=Depends(get_db)):
    """
    Elimina un departamento. **No se permite** si tiene empleados
    (la FK lo impide y devolvemos un mensaje claro).
    """
    cursor = db.cursor()
    try:
        cursor.execute(
            "SELECT * FROM departamentos WHERE departamento_id = ?",
            (departamento_id,),
        )
        dept = fetch_one(cursor)
        if not dept:
            raise HTTPException(404, "Departamento no encontrado.")

        cursor.execute(
            "DELETE FROM departamentos WHERE departamento_id = ?",
            (departamento_id,),
        )
        db.commit()
        return {"mensaje": "Departamento eliminado.", "departamento": dept}
    except pyodbc.IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "No se puede eliminar: el departamento tiene empleados asignados.",
        )
    finally:
        cursor.close()
