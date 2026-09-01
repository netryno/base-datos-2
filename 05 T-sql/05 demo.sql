/* ============================================================
   PARTE 2 - "MINI IA": generador de refranes con cadena de Markov
   Version compatible con SQL Server 2016
   (sin STRING_AGG, sin NEWID/TOP dentro de funciones)
   ============================================================ */

-- 2.1 Corpus (el "dataset de entrenamiento")
IF OBJECT_ID('dbo.refranes_corpus', 'U') IS NULL
CREATE TABLE refranes_corpus (
    id    INT IDENTITY(1,1) PRIMARY KEY,
    texto VARCHAR(200) NOT NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM refranes_corpus)
INSERT INTO refranes_corpus (texto) VALUES
('mas vale pajaro en mano que ciento volando'),
('perro que ladra no muerde'),
('a caballo regalado no se le mira el diente'),
('el que madruga dios lo ayuda'),
('no hay mal que por bien no venga'),
('cria cuervos y te sacaran los ojos'),
('donde hay humo hay fuego'),
('el que a buen arbol se arrima buena sombra le cobija'),
('agua que no has de beber dejala correr'),
('camaron que se duerme se lo lleva la corriente'),
('mas vale tarde que nunca'),
('cada perro con su hueso'),
('al mal tiempo buena cara'),
('quien mucho abarca poco aprieta'),
('el que no arriesga no gana'),
('dime con quien andas y te dire quien eres'),
('ojos que no ven corazon que no siente'),
('en boca cerrada no entran moscas'),
('mas sabe el diablo por viejo que por diablo'),
('no todo lo que brilla es oro');
GO

-- 2.2 Tokenizador: separa un texto en palabras con su posicion
IF OBJECT_ID('dbo.fn_tokenizar', 'TF') IS NOT NULL
    DROP FUNCTION dbo.fn_tokenizar;
GO
CREATE FUNCTION dbo.fn_tokenizar (@texto VARCHAR(200))
RETURNS @tabla TABLE (posicion INT, palabra VARCHAR(50))
AS
BEGIN
    DECLARE @xml XML = CAST('<p>' + REPLACE(@texto, ' ', '</p><p>') + '</p>' AS XML);
    INSERT INTO @tabla (posicion, palabra)
    SELECT ROW_NUMBER() OVER (ORDER BY (SELECT NULL)), T.c.value('.', 'VARCHAR(50)')
    FROM @xml.nodes('/p') AS T(c);
    RETURN;
END;
GO

-- 2.3 Bigramas: pares (palabra_actual -> palabra_siguiente), el "modelo entrenado"
IF OBJECT_ID('dbo.bigramas', 'U') IS NOT NULL DROP TABLE dbo.bigramas;
GO
CREATE TABLE bigramas (
    palabra_actual    VARCHAR(50) NOT NULL,
    palabra_siguiente VARCHAR(50) NULL
);
GO

INSERT INTO bigramas (palabra_actual, palabra_siguiente)
SELECT t1.palabra, t2.palabra
FROM refranes_corpus r
CROSS APPLY dbo.fn_tokenizar(r.texto) t1
OUTER APPLY (
    SELECT palabra FROM dbo.fn_tokenizar(r.texto) t2b
    WHERE t2b.posicion = t1.posicion + 1
) t2;
GO

-- Vistazo al "modelo" antes de usarlo (bueno para mostrar en clase)
-- SELECT * FROM bigramas ORDER BY palabra_actual;


-- 2.4 Generador: PROCEDIMIENTO con WHILE (NEWID/TOP solo se permiten aqui, no en funciones)
IF OBJECT_ID('dbo.sp_generar_frase_ia', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_generar_frase_ia;
GO
CREATE PROCEDURE dbo.sp_generar_frase_ia
    @palabra_inicio VARCHAR(50),
    @max_palabras   INT,
    @frase          VARCHAR(400) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @actual    VARCHAR(50) = LOWER(@palabra_inicio);
    DECLARE @siguiente VARCHAR(50);
    DECLARE @paso      INT = 1;

    DECLARE @cadena TABLE (paso INT, palabra VARCHAR(50));
    INSERT INTO @cadena VALUES (1, @actual);

    WHILE @paso < @max_palabras
    BEGIN
        SET @siguiente = NULL;

        SELECT TOP 1 @siguiente = palabra_siguiente
        FROM bigramas
        WHERE palabra_actual = @actual AND palabra_siguiente IS NOT NULL
        ORDER BY NEWID();

        IF @siguiente IS NULL BREAK;

        SET @paso = @paso + 1;
        INSERT INTO @cadena VALUES (@paso, @siguiente);
        SET @actual = @siguiente;
    END

    -- Concatenacion manual (equivalente a STRING_AGG, que no existe en 2016)
    SET @frase = '';
    SELECT @frase = @frase + palabra + ' '
    FROM @cadena
    ORDER BY paso;

    SET @frase = RTRIM(@frase);
END;
GO


-- 2.5 Procedimiento de cara al usuario: le das una palabra, te da dos versiones
IF OBJECT_ID('dbo.sp_refran_con_ia', 'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_refran_con_ia;
GO
CREATE PROCEDURE dbo.sp_refran_con_ia
    @palabra VARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;

    -- Version 1: refran autentico del corpus que contiene la palabra
    SELECT texto AS refran_autentico
    FROM refranes_corpus
    WHERE texto LIKE '%' + @palabra + '%';

    -- Version 2: frase generada por el modelito (cadena de Markov)
    DECLARE @frase VARCHAR(400);
    EXEC dbo.sp_generar_frase_ia
        @palabra_inicio = @palabra,
        @max_palabras   = 8,
        @frase          = @frase OUTPUT;

    SELECT @frase AS frase_generada_por_ia;
END;
GO

-- Prueba:
-- EXEC dbo.sp_refran_con_ia 'perro';
-- EXEC dbo.sp_refran_con_ia 'agua';
-- EXEC dbo.sp_refran_con_ia 'mal';
-- EXEC dbo.sp_refran_con_ia 'madruga';
/* Preguntas para la clase:
   1. Por que a veces la frase generada no tiene sentido gramatical?
      (el modelo solo mira 1 palabra de contexto -> bigramas)
   2. Que pasaria si en vez de 1 palabra de contexto usaramos 2 o 3?
      (trigrama / n-grama -> mas coherente pero necesita mas datos)
   3. Por que NEWID() y no un ORDER BY fijo?
      (sin azar, siempre generaria la misma frase -> "temperatura 0")
   4. Por que NEWID() funciona en el procedimiento pero NO en una funcion?
      (las funciones deben ser deterministas: mismo input -> mismo output.
       NEWID() rompe esa garantia, por eso SQL Server lo bloquea ahi)
*/