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