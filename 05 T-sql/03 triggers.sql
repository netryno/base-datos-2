/*===========================================================================
  3) TRIGGER: trg_empleado_nombre_editado
  ---------------------------------------------------------------------------
  AFTER INSERT sobre dbo.empleados: añade automáticamente el sufijo
  '_editado_trigger' al nombre de cada nuevo empleado.

  Se usa UPDATE sobre la tabla real mediante un JOIN a la tabla inserted,
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

  NOTA: PRINT solo admite expresiones escalares; por eso guardamos los
  valores en variables (@IdGenerado, @NombreFinal) ANTES de imprimirlos.
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

    DECLARE @NuevoID TABLE (empleado_id INT);

    BEGIN TRY
        BEGIN TRANSACTION;

        IF NOT EXISTS (SELECT 1 FROM dbo.departamentos
                       WHERE departamento_id = @departamento_id)
        BEGIN
            RAISERROR('El departamento_id %d no existe.', 16, 1, @departamento_id);
        END

        INSERT INTO dbo.empleados (empleado_nombre, puesto, departamento_id)
        OUTPUT INSERTED.empleado_id INTO @NuevoID (empleado_id)
        VALUES (@empleado_nombre, @puesto, @departamento_id);

        COMMIT TRANSACTION;

        -- Variables escalares (PRINT no admite subconsultas)
        DECLARE @IdGenerado  INT          = (SELECT empleado_id FROM @NuevoID);
        DECLARE @NombreFinal VARCHAR(72);

        SELECT @NombreFinal = empleado_nombre
        FROM   dbo.empleados
        WHERE  empleado_id = @IdGenerado;

        -- Devolver el registro final (nombre ya editado por el trigger)
        SELECT  e.empleado_id,
                e.empleado_nombre AS nombre_final_editado,
                e.puesto,
                e.departamento_id
        FROM    dbo.empleados AS e
        WHERE   e.empleado_id = @IdGenerado;

        PRINT '==========================================================';
        PRINT '  EMPLEADO REGISTRADO (nombre editado por trigger)';
        PRINT '  ID           : ' + CAST(@IdGenerado AS VARCHAR(10));
        PRINT '  Nombre final : ' + @NombreFinal;
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
  ejemplo al inicio. Luego se prueba: el trigger (vía sp_insertar_empleado),
  el procedimiento de préstamo y la función.
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