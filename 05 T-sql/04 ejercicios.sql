
/*===========================================================================
  PRUEBAS (opcionales - descomentar para ejecutar)
  ---------------------------------------------------------------------------
  -- Listar el top 10 de empleados con más préstamos:
  -- SELECT * FROM dbo.fn_top10_empleados_prestamos();

  -- Insertar un préstamo:
  -- EXEC dbo.sp_insertar_prestamo @empleado_id = 1, @herramienta_id = 1;

  -- Insertar un empleado (el trigger le añadirá '_editado_trigger'):
  -- EXEC dbo.sp_insertar_empleado
  --      @empleado_nombre   = 'Juan Perez',
  --      @puesto            = 'Tecnico',
  --      @departamento_id   = 1;
===========================================================================*/


/*===========================================================================
  ejercicio.sql
  ---------------------------------------------------------------------------
  Objetos T-SQL (SQL Server) para la BD bd_herramientas:
    1) Función TVF   : fn_top10_empleados_prestamos
                       -> Top 10 empleados con más préstamos de herramientas.
    2) Procedimiento : sp_insertar_prestamo
                       -> Inserta un préstamo y muestra claramente el último
                          ID registrado en el mensaje.
    3) Trigger        : trg_empleado_nombre_editado
                       -> Al crear un nuevo empleado, añade automáticamente
                          el sufijo '_editado_trigger' a su nombre.
    4) Procedimiento : sp_insertar_empleado
                       -> Permite insertar un empleado (dispara el trigger).
  ---------------------------------------------------------------------------
  Esquema de referencia (ya creado por la app en app/database.py):
    departamentos(departamento_id, departamento_codigo, departamento_nombre)
    empleados    (empleado_id, empleado_nombre, puesto, departamento_id)
    herramientas (herramienta_id, codigo_inventario, nombre, estado)
    prestamos    (prestamo_id, empleado_id, herramienta_id,
                  fecha_prestamo, fecha_devolucion)
===========================================================================*/

USE bd_herramientas;
GO


/*===========================================================================
  1) FUNCIÓN: fn_top10_empleados_prestamos
  ---------------------------------------------------------------------------
  Devuelve el TOP 10 de empleados con mayor número de préstamos de
  herramientas. Para cada empleado muestra: nombre, puesto, departamento,
  total de préstamos y cuántos siguen abiertos (sin devolución).
===========================================================================*/
IF OBJECT_ID('dbo.fn_top10_empleados_prestamos', 'TF') IS NOT NULL
    DROP FUNCTION dbo.fn_top10_empleados_prestamos;
GO

CREATE FUNCTION dbo.fn_top10_empleados_prestamos ()
RETURNS TABLE
AS
RETURN
(
    SELECT TOP (10)
        e.empleado_id,
        e.empleado_nombre,
        e.puesto,
        d.departamento_nombre,
        COUNT(p.prestamo_id)                 AS total_prestamos,
        SUM(CASE WHEN p.fecha_devolucion IS NULL
                 THEN 1 ELSE 0 END)          AS prestamos_abiertos
    FROM   dbo.empleados    AS e
    INNER JOIN dbo.prestamos    AS p ON p.empleado_id    = e.empleado_id
    LEFT  JOIN dbo.departamentos AS d ON d.departamento_id = e.departamento_id
    GROUP BY e.empleado_id, e.empleado_nombre, e.puesto, d.departamento_nombre
    ORDER BY total_prestamos DESC, prestamos_abiertos DESC
);
GO


/*===========================================================================
  2) PROCEDIMIENTO: sp_insertar_prestamo
  ---------------------------------------------------------------------------
  Inserta un nuevo préstamo de herramienta y, mediante OUTPUT INSERTED,
  captura el último ID registrado, devolviéndolo como conjunto de resultados
  e imprimiendo un mensaje claro con ese ID.
===========================================================================*/
IF OBJECT_ID('dbo.sp_insertar_prestamo', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_insertar_prestamo;
GO

CREATE PROCEDURE dbo.sp_insertar_prestamo
    @empleado_id     INT,
    @herramienta_id  INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @NuevoID TABLE (prestamo_id INT);

    BEGIN TRY
        BEGIN TRANSACTION;

        -- Validaciones básicas de existencia
        IF NOT EXISTS (SELECT 1 FROM dbo.empleados
                       WHERE empleado_id = @empleado_id)
        BEGIN
            RAISERROR('El empleado_id %d no existe.', 16, 1, @empleado_id);
        END

        IF NOT EXISTS (SELECT 1 FROM dbo.herramientas
                       WHERE herramienta_id = @herramienta_id)
        BEGIN
            RAISERROR('La herramienta_id %d no existe.', 16, 1, @herramienta_id);
        END

        -- Validación: la herramienta no debe tener un préstamo abierto
        IF EXISTS (SELECT 1 FROM dbo.prestamos
                   WHERE herramienta_id = @herramienta_id
                     AND fecha_devolucion IS NULL)
        BEGIN
            RAISERROR('La herramienta %d ya tiene un préstamo abierto.',
                      16, 1, @herramienta_id);
        END

        -- Inserción capturando el último ID generado
        INSERT INTO dbo.prestamos (empleado_id, herramienta_id, fecha_prestamo)
        OUTPUT INSERTED.prestamo_id INTO @NuevoID (prestamo_id)
        VALUES (@empleado_id, @herramienta_id, GETDATE());

        COMMIT TRANSACTION;

        -- Mensaje claro con el último ID registrado
        DECLARE @IdGenerado INT = (SELECT prestamo_id FROM @NuevoID);

        PRINT '==========================================================';
        PRINT '  PRESTAMO REGISTRADO CORRECTAMENTE';
        PRINT '  Ultimo ID registrado (prestamo_id): ' + CAST(@IdGenerado AS VARCHAR(10));
        PRINT '  Empleado     : ' + CAST(@empleado_id    AS VARCHAR(10));
        PRINT '  Herramienta  : ' + CAST(@herramienta_id AS VARCHAR(10));
        PRINT '  Fecha        : ' + CONVERT(VARCHAR(19), GETDATE(), 120);
        PRINT '==========================================================';

        -- Devolver el último ID como conjunto de resultados
        SELECT @IdGenerado AS ultimo_prestamo_id;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;

        PRINT '==========================================================';
        PRINT '  ERROR AL REGISTRAR EL PRESTAMO';
        PRINT '  Mensaje: ' + ERROR_MESSAGE();
        PRINT '==========================================================';

        -- Re-lanzar para que el cliente también lo vea
        ;THROW;
    END CATCH
END;
GO


/*===========================================================================
  3) TRIGGER: trg_empleado_nombre_editado
  ---------------------------------------------------------------------------
  AFTER INSERT sobre dbo.empleados: añade automáticamente el sufijo
  '_editado_trigger' al nombre de cada nuevo empleado.

  Se usa UPDATE sobre la tabla inserted mediante un JOIN a la tabla real,
  actualizando solo las filas recién insertadas (evita recursividad).
===========================================================================*/
IF OBJECT_ID('dbo.trg_empleado_nombre_editado', 'TR') IS NOT NULL
    DROP TRIGGER dbo.trg_empleado_nombre_editado;
GO

CREATE TRIGGER dbo.trg_empleado_nombre_editado
ON dbo.empleados
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE e
    SET    e.empleado_nombre = e.empleado_nombre + '_editado_trigger'
    FROM   dbo.empleados AS e
    INNER JOIN inserted  AS i ON i.empleado_id = e.empleado_id;

    PRINT 'Trigger trg_empleado_nombre_editado: '
          + CAST(@@ROWCOUNT AS VARCHAR(5))
          + ' empleado(s) con sufijo _editado_trigger aplicado.';
END;
GO


/*===========================================================================
  4) PROCEDIMIENTO: sp_insertar_empleado
  ---------------------------------------------------------------------------
  Permite insertar un nuevo empleado. Al hacerlo, el trigger anterior
  modificará automáticamente el nombre añadiendo '_editado_trigger'.
  Devuelve el ID generado y el nombre final (ya editado por el trigger).
===========================================================================*/
IF OBJECT_ID('dbo.sp_insertar_empleado', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_insertar_empleado;
GO

CREATE PROCEDURE dbo.sp_insertar_empleado
    @empleado_nombre   VARCHAR(60),
    @puesto            VARCHAR(50),
    @departamento_id   INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @NuevoID TABLE (empleado_id INT, empleado_nombre VARCHAR(72));

    BEGIN TRY
        BEGIN TRANSACTION;

        IF NOT EXISTS (SELECT 1 FROM dbo.departamentos
                       WHERE departamento_id = @departamento_id)
        BEGIN
            RAISERROR('El departamento_id %d no existe.', 16, 1, @departamento_id);
        END

        INSERT INTO dbo.empleados (empleado_nombre, puesto, departamento_id)
        OUTPUT INSERTED.empleado_id, INSERTED.empleado_nombre
            INTO @NuevoID (empleado_id, empleado_nombre)
        VALUES (@empleado_nombre, @puesto, @departamento_id);

        COMMIT TRANSACTION;

        -- El trigger ya modificó el nombre; lo releemos para mostrar el final
        SELECT  e.empleado_id,
                e.empleado_nombre AS nombre_final_editado,
                e.puesto,
                e.departamento_id
        FROM    dbo.empleados AS e
        WHERE   e.empleado_id = (SELECT empleado_id FROM @NuevoID);

        PRINT '==========================================================';
        PRINT '  EMPLEADO REGISTRADO (nombre editado por trigger)';
        PRINT '  ID            : '
              + CAST((SELECT empleado_id FROM @NuevoID) AS VARCHAR(10));
        PRINT '  Nombre final : '
              + (SELECT empleado_nombre FROM dbo.empleados
                WHERE empleado_id = (SELECT empleado_id FROM @NuevoID));
        PRINT '==========================================================';
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;

        PRINT '==========================================================';
        PRINT '  ERROR AL REGISTRAR EL EMPLEADO';
        PRINT '  Mensaje: ' + ERROR_MESSAGE();
        PRINT '==========================================================';
        ;THROW;
    END CATCH
END;
GO


/*===========================================================================
  PRUEBAS
  ---------------------------------------------------------------------------
  Bloque de prueba ejecutable. Pre-condición: deben existir al menos un
  departamento y una herramienta en la BD. Si no existen, se crean datos de
  ejemplo al inicio. Luego se prueba: la función, el procedimiento de
  préstamo, el procedimiento de empleado (que dispara el trigger) y se
  verifica el resultado del trigger.
===========================================================================*/

-- 0) Datos de apoyo (solo si no existen aún) -------------------------------
IF NOT EXISTS (SELECT 1 FROM dbo.departamentos)
BEGIN
    INSERT INTO dbo.departamentos (departamento_codigo, departamento_nombre)
    VALUES ('D01', 'Mantenimiento');
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.herramientas)
BEGIN
    INSERT INTO dbo.herramientas (codigo_inventario, nombre, estado)
    VALUES ('H-001', 'Taladro', 'nuevo'),
           ('H-002', 'Llave inglesa', 'usado');
END
GO

-- 1) Probar el TRIGGER: insertar un empleado (el trigger añade el sufijo) -
PRINT '>>> PRUEBA TRIGGER: insertando empleado...';
EXEC dbo.sp_insertar_empleado
     @empleado_nombre   = 'Juan Perez',
     @puesto            = 'Tecnico',
     @departamento_id   = 1;
GO

-- Verificar que el trigger modificó el nombre:
PRINT '>>> Verificacion del trigger (nombre debe llevar _editado_trigger):';
SELECT  empleado_id,
        empleado_nombre,
        puesto,
        departamento_id
FROM    dbo.empleados
ORDER BY empleado_id DESC;
GO

-- 2) Probar el PROCEDIMIENTO de préstamo ------------------------------------
PRINT '>>> PRUEBA PROCEDIMIENTO: insertando prestamo...';
DECLARE @EmpId INT = (SELECT TOP 1 empleado_id FROM dbo.empleados ORDER BY empleado_id DESC);
DECLARE @HerId INT = (SELECT TOP 1 herramienta_id FROM dbo.herramientas ORDER BY herramienta_id);

EXEC dbo.sp_insertar_prestamo
     @empleado_id    = @EmpId,
     @herramienta_id = @HerId;
GO

-- 3) Probar la FUNCION: top 10 empleados con más préstamos ------------------
PRINT '>>> PRUEBA FUNCION: top 10 empleados con mas prestamos:';
SELECT * FROM dbo.fn_top10_empleados_prestamos();
GO
