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