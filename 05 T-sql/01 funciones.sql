-- FUNCION: devuelve un valor, se puede usar dentro de un SELECT
IF OBJECT_ID('dbo.fn_factorial', 'FN') IS NOT NULL
    DROP FUNCTION dbo.fn_factorial;
GO
CREATE FUNCTION dbo.fn_factorial (@n INT)
RETURNS BIGINT
AS
BEGIN
    DECLARE @resultado BIGINT = 1;
    DECLARE @i INT = 1;

    IF @n < 0 RETURN NULL;  -- factorial no definido para negativos

    WHILE @i <= @n
    BEGIN
        SET @resultado = @resultado * @i;
        SET @i = @i + 1;
    END

    RETURN @resultado;
END;
GO

-- Uso: se puede meter directo en un SELECT, como cualquier columna
SELECT dbo.fn_factorial(5) AS factorial_de_5;
SELECT n, dbo.fn_factorial(n) AS factorial
FROM (VALUES (1),(2),(3),(4),(5)) AS t(n);



--- recursivo (para mostrar que también se puede, aunque en SQL Server rara vez conviene por performance)
IF OBJECT_ID('dbo.fn_factorial_recursivo', 'FN') IS NOT NULL
    DROP FUNCTION dbo.fn_factorial_recursivo;
GO
CREATE FUNCTION dbo.fn_factorial_recursivo (@n INT)
RETURNS BIGINT
AS
BEGIN
    IF @n <= 1 RETURN 1;
    RETURN @n * dbo.fn_factorial_recursivo(@n - 1);
END;
GO

-- para usar,
SELECT dbo.fn_factorial_recursivo(5) AS factorial_de_5;

--Ojo: SQL Server limita la recursión a 32 niveles por defecto en funciones escalares recursivas