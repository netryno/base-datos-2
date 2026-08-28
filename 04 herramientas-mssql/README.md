# Control de Herramientas — Python + SQL Server

API con **FastAPI** y **SQL Server** para gestionar el préstamo de herramientas
de una empresa de construcción. Pensada para enseñar SQL, modelo
Entidad-Relación y el trabajo con SQL Server.

## Enunciado del problema

**Control de Herramientas de una Empresa (3 Entidades)** — 
Ideal para entender la asignación de inventario y dependencias directas.

Una empresa de construcción quiere controlar el uso de sus herramientas de
trabajo. Cuenta con **Empleados**, de los cuales se registra el ID de
empleado, nombre y puesto. La empresa posee **Herramientas** de las que se
conoce un código de inventario, nombre de la herramienta y su estado (nuevo,
usado, en reparación). Cada empleado pertenece a un único **Departamento**
(como "Carpintería" o "Plomería"), del cual se guarda un código de
departamento y el nombre.

- Un departamento tiene muchos empleados, pero un empleado pertenece a un
  solo departamento.
- Un empleado puede solicitar prestadas varias herramientas a la vez, y una
  herramienta específica solo puede estar prestada a un empleado a la vez.

## Modelo Entidad-Relación

```
DEPARTAMENTO 1 ─── N EMPLEADO N ─── M HERRAMIENTA
```

- Un **departamento** tiene muchos empleados; un **empleado** pertenece a un
  solo departamento.
- Un **empleado** puede pedir prestadas varias herramientas a la vez; una
  **herramienta** solo puede estar prestada a un empleado a la vez (regla
  cumplida con un **índice único filtrado** en SQL Server).

> **Nota sobre la cardinalidad Empleado ↔ Herramienta (N:M):** la relación es
> N:M porque un empleado usa muchas herramientas y una herramienta la usan
> muchos empleados *a lo largo del tiempo*. La frase "una herramienta solo
> prestada a un empleado **a la vez**" es una restricción de simultaneidad,
> no de cardinalidad: se cumple con el índice único filtrado
> `ux_prestamos_herramienta_activa` (solo un préstamo abierto por herramienta),
> pero la herramienta puede pasar por muchos empleados distintos a lo largo
> del tiempo. Por eso se modela con la tabla puente `prestamos`.

## ¿Qué hace el servicio?

1. **Setup** — crea la base de datos y las tablas base si no existen, y carga
   datos iniciales (catálogos estáticos + empleados dinámicos).
2. **CRUD Departamento** — crear, listar, obtener, actualizar, eliminar.
3. **CRUD Herramienta** — crear, listar (con estado de préstamo), obtener,
   actualizar, eliminar.
4. **CRUD Empleado** — crear, listar (con departamento), obtener (con
   herramientas prestadas), actualizar, eliminar.
5. **Préstamos** — prestar una herramienta a un empleado y devolverla
   (demuestra la relación N:M).

## Estructura del proyecto

```
app/
  config.py        → conexión (variables de entorno)
  database.py      → init_db(), get_db(), helpers de filas + esquema DDL
  schemas.py       → modelos Pydantic (validación + Swagger)
  seeders.py       → catálogos estáticos + seeder dinámico de empleados
  routers/
    setup.py           → 1) init-db  2) seed-catalogos  3) seed-empleados
    departamentos.py   → CRUD
    herramientas.py    → CRUD
    empleados.py       → CRUD
    prestamos.py       → préstamo/devolución (relación N:M)
  main.py          → app + startup + inclusión de routers
```

## Cómo levantarlo

> Requiere un SQL Server accesible (por ejemplo, otro contenedor Docker
> publicado en `localhost:1433`).

1. Construir y arrancar la API:

   ```bash
   docker compose up --build
   ```

2. Abrir Swagger en:

   ```
   http://localhost:8075/docs
   ```

3. Flujo recomendado desde Swagger:

   - `POST /setup/init-db` → crea la BD y las tablas (también se ejecuta solo
     al arrancar).
   - `POST /setup/seed-catalogos` → carga departamentos y herramientas.
   - `POST /setup/seed-empleados?cantidad=20` → carga 20 empleados.
   - Usar los CRUD de `/departamentos`, `/herramientas`, `/empleados`.
   - `POST /prestamos` → prestar y devolver herramientas.

## Configuración (variables de entorno)

Definidas en `docker-compose.yml`:

| Variable      | Valor por defecto     | Descripción                |
|---------------|-----------------------|----------------------------|
| `DB_HOST`     | `host.docker.internal`| Host de SQL Server         |
| `DB_PORT`     | `1433`                | Puerto de SQL Server       |
| `DB_USER`     | `sa`                  | Usuario                    |
| `DB_PASSWORD` | `AlumnoSql2025!`      | Contraseña                 |
| `DB_NAME`     | `bd_herramientas`     | Base de datos a usar/crear |

La API escucha en el puerto **8075** del host.
