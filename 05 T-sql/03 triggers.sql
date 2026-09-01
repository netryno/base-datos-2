
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

