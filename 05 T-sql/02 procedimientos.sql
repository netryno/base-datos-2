--2 PROCEDIMIENTO: no "devuelve" un valor para usar en SELECT,
-- pero puede usar OUTPUT, imprimir resultados, o manejar errores
IF OBJECT_ID('dbo.sp_factorial', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_factorial;
GO
CREATE PROCEDURE dbo.sp_factorial
    @n          INT,
    @resultado  BIGINT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    IF @n < 0
    BEGIN
        RAISERROR('El factorial no esta definido para numeros negativos.', 16, 1);
        RETURN;
    END

    SET @resultado = 1;
    DECLARE @i INT = 1;

    WHILE @i <= @n
    BEGIN
        SET @resultado = @resultado * @i;
        SET @i = @i + 1;
    END
END;
GO

-- Uso: hay que declarar una variable para "recibir" el resultado
DECLARE @res BIGINT;
EXEC dbo.sp_factorial @n = 5, @resultado = @res OUTPUT;
SELECT @res AS factorial_de_5;






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
