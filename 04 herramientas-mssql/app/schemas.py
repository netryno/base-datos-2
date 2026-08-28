"""
===========================================================================
Modelos Pydantic (validación de entrada y documentación Swagger)
===========================================================================

Estos modelos NO son las tablas de la BD; son los "contratos" de la API:
validan lo que llega en el body de cada petición y alimentan los ejemplos
de Swagger. Cada modelo lleva descripciones para que la documentación sea
clara.
"""

from datetime import date, datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator
import re


# ---------------------------------------------------------------------------
# Departamento
# ---------------------------------------------------------------------------

class DepartamentoCreate(BaseModel):
    departamento_codigo: str = Field(
        ..., min_length=1, max_length=10,
        examples=["CAR"],
        description="Código corto del departamento (único)."
    )
    departamento_nombre: str = Field(
        ..., min_length=1, max_length=50,
        examples=["Carpintería"],
        description="Nombre del departamento."
    )

    @field_validator('departamento_codigo', 'departamento_nombre')
    @classmethod
    def sin_espacios_extremos(cls, v):
        return v.strip()


class DepartamentoUpdate(BaseModel):
    departamento_codigo: Optional[str] = Field(
        None, min_length=1, max_length=10, examples=["CAR"]
    )
    departamento_nombre: Optional[str] = Field(
        None, min_length=1, max_length=50, examples=["Carpintería"]
    )

    @field_validator('departamento_codigo', 'departamento_nombre')
    @classmethod
    def sin_espacios_extremos(cls, v):
        return v.strip() if v else v


class DepartamentoOut(BaseModel):
    departamento_id: int
    departamento_codigo: str
    departamento_nombre: str


# ---------------------------------------------------------------------------
# Empleado
# ---------------------------------------------------------------------------

class EmpleadoCreate(BaseModel):
    empleado_nombre: str = Field(
        ..., min_length=1, max_length=60,
        examples=["Juan Pérez"],
        description="Nombre completo del empleado."
    )
    puesto: str = Field(
        ..., min_length=1, max_length=50,
        examples=["Operario"],
        description="Puesto que ocupa el empleado."
    )
    departamento_id: int = Field(
        ..., gt=0,
        examples=[1],
        description="ID del departamento al que pertenece (único)."
    )

    @field_validator('empleado_nombre', 'puesto')
    @classmethod
    def solo_letras(cls, v):
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', v):
            raise ValueError('Solo se permiten letras y espacios')
        return v.strip()


class EmpleadoUpdate(BaseModel):
    empleado_nombre: Optional[str] = Field(None, min_length=1, max_length=60, examples=["Juan Pérez"])
    puesto: Optional[str] = Field(None, min_length=1, max_length=50, examples=["Operario"])
    departamento_id: Optional[int] = Field(None, gt=0, examples=[1])


class EmpleadoOut(BaseModel):
    empleado_id: int
    empleado_nombre: str
    puesto: str
    departamento_id: int


# ---------------------------------------------------------------------------
# Herramienta
# ---------------------------------------------------------------------------

# Los estados permitidos coinciden con el CHECK de la tabla.
EstadoHerramienta = Literal['nuevo', 'usado', 'en reparacion']


class HerramientaCreate(BaseModel):
    codigo_inventario: str = Field(
        ..., min_length=1, max_length=20,
        examples=["HERR-001"],
        description="Código de inventario (único)."
    )
    nombre: str = Field(
        ..., min_length=1, max_length=50,
        examples=["Taladro"],
        description="Nombre de la herramienta."
    )
    estado: EstadoHerramienta = Field(
        ..., examples=["nuevo"],
        description="Estado: 'nuevo', 'usado' o 'en reparacion'."
    )


class HerramientaUpdate(BaseModel):
    codigo_inventario: Optional[str] = Field(None, min_length=1, max_length=20, examples=["HERR-001"])
    nombre: Optional[str] = Field(None, min_length=1, max_length=50, examples=["Taladro"])
    estado: Optional[EstadoHerramienta] = Field(None, examples=["usado"])


class HerramientaOut(BaseModel):
    herramienta_id: int
    codigo_inventario: str
    nombre: str
    estado: str


# ---------------------------------------------------------------------------
# Préstamo (relación N:M)
# ---------------------------------------------------------------------------

class PrestamoCreate(BaseModel):
    empleado_id: int = Field(..., gt=0, examples=[1], description="Empleado que pide la herramienta.")
    herramienta_id: int = Field(..., gt=0, examples=[1], description="Herramienta a prestar.")


class DevolucionOut(BaseModel):
    prestamo_id: int
    empleado_id: int
    herramienta_id: int
    fecha_prestamo: datetime
    fecha_devolucion: Optional[datetime]
