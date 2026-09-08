### Transacciones

Una transacción es una secuencia de una o mas operaciones de base de datos que se ejecutan como una unidad indivisible

ATOMICIDAD

Garantiza sque las operaciones se ejecuten de manera consistente, es decir que se cumplan todas o ninguna de las operaciones.

ACID (Atomicidad, Consistencia, Aislamiento (no se interfierene entre si) , Durabilidad (permanente)

    Propiedades ACID:
        Atomicidad: Todo o nada
        
        Consistencia: Los datos siempre quedan en estado válido
        
        Aislamiento: Las transacciones no se afectan entre sí
        
        Durabilidad: Los cambios persisten después del COMMIT

#sql

```sql
CREATE PROCEDURE sp_crear_tablas_y_datos_iniciales
AS
BEGIN
    -- 1) Crear tablas si no existen (fraternidad primero, ya no depende de persona)
    IF OBJECT_ID('dbo.fraternidad', 'U') IS NULL
    BEGIN
        CREATE TABLE fraternidad (
            id_fraternidad INT IDENTITY PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            fecha_fundacion DATE
        );
    END

    IF OBJECT_ID('dbo.persona', 'U') IS NULL
    BEGIN
        CREATE TABLE persona (
            id_persona INT IDENTITY PRIMARY KEY,
            nombre VARCHAR(80) NOT NULL,
            ci VARCHAR(15) NOT NULL UNIQUE,
            cargo VARCHAR(40),
            id_fraternidad INT NOT NULL FOREIGN KEY REFERENCES fraternidad(id_fraternidad)
        );
    END

    IF OBJECT_ID('dbo.entrada', 'U') IS NULL
    BEGIN
        CREATE TABLE entrada (
            id_entrada INT IDENTITY PRIMARY KEY,
            nombre_evento VARCHAR(100) NOT NULL,
            anio INT NOT NULL,
            fecha DATE NOT NULL
        );
    END

    IF OBJECT_ID('dbo.inscripcion', 'U') IS NULL
    BEGIN
        CREATE TABLE inscripcion (
            id_inscripcion INT IDENTITY PRIMARY KEY,
            id_fraternidad INT NOT NULL FOREIGN KEY REFERENCES fraternidad(id_fraternidad),
            id_entrada INT NOT NULL FOREIGN KEY REFERENCES entrada(id_entrada),
            numero_participantes INT NOT NULL,
            fecha_inscripcion DATE NOT NULL DEFAULT GETDATE(),
            estado VARCHAR(15) NOT NULL CHECK (estado IN ('activa','cancelada'))
        );
    END

    -- 2) Insertar datos fijos, solo si cada tabla está vacía
    IF NOT EXISTS (SELECT 1 FROM fraternidad)
    BEGIN
        INSERT INTO fraternidad (nombre, fecha_fundacion) VALUES
        ('Fraternidad Los Diablos', '1985-05-10'),
        ('Caporales San Simón', '1998-03-20');
    END

    IF NOT EXISTS (SELECT 1 FROM persona)
    BEGIN
        INSERT INTO persona (nombre, ci, cargo, id_fraternidad) VALUES
        ('Juan Pérez Quispe', '4521367', 'Presidente', 1),
        ('Ana Mamani Colque', '5871234', 'Bailarín', 1),
        ('María Fernández Rojas', '6987412', 'Presidenta', 2),
        ('Luis Gómez Torrez', '7412589', 'Bailarín', 2);
    END

    IF NOT EXISTS (SELECT 1 FROM entrada)
    BEGIN
        INSERT INTO entrada (nombre_evento, anio, fecha) VALUES
        ('Entrada Virgen de Guadalupe', 2025, '2025-09-08'),
        ('Entrada Virgen de Guadalupe', 2026, '2026-09-08');
    END

    IF NOT EXISTS (SELECT 1 FROM inscripcion)
    BEGIN
        INSERT INTO inscripcion (id_fraternidad, id_entrada, numero_participantes, estado) VALUES
        (1, 1, 120, 'activa'),
        (2, 1, 90, 'activa');
    END
END;
GO   
```

```sql
-- Prueba
EXEC sp_crear_tablas_y_datos_iniciales;
SELECT * FROM fraternidad;
SELECT * FROM persona;   -- se ve que hay 2 personas por cada fraternidad
SELECT * FROM entrada;
SELECT * FROM inscripcion;

-- Segunda ejecución: no debe duplicar datos ni fallar al recrear tablas
EXEC sp_crear_tablas_y_datos_iniciales;
```

Conceptos base que vas a usar

    BEGIN TRANSACTION / COMMIT TRANSACTION / ROLLBACK TRANSACTION: abren, confirman y revierten un bloque de trabajo.
    TRY...CATCH: captura errores dentro de la transacción para decidir si hago COMMIT o ROLLBACK
    
    
    XACT_ABORT ON: si algo falla, SQL Server aborta toda la transacción automáticamente (evita transacciones "zombis" a medio confirmar).
    
    
    @@TRANCOUNT: contador de transacciones abiertas; útil cuando un procedimiento con transacción llama a otro procedimiento con transacción (transacciones anidadas).
    
    
    SAVE TRANSACTION nombre: crea un "punto de guardado" dentro de una transacción, para revertir solo una parte sin perder todo el trabajo previo.
    
    
    Propiedades ACID: Atomicidad, Consistencia, Aislamiento, Durabilidad — la razón de ser de todo esto.

  
### Ejercicio 1 — Transacción simple con COMMIT

La Alcaldía quiere registrar una nueva fraternidad, "Morenada Central", fundada el 2010-04-15. Se pide que la inserción quede envuelta en una transacción explícita: si todo sale bien, se confirma; si algo falla, no debe quedar nada a medias.

```sql
BEGIN TRY
    BEGIN TRANSACTION;

    INSERT INTO fraternidad (nombre, fecha_fundacion)
    VALUES ('Morenada Central', '2010-04-15');

    COMMIT TRANSACTION;
    PRINT 'Fraternidad registrada correctamente.';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    PRINT 'Error al registrar la fraternidad: ' + ERROR_MESSAGE();
END CATCH;
```





Idea clave: este es el patrón base — TRY para el trabajo, CATCH para deshacerlo si algo revienta.



### Ejercicio 2 — ROLLBACK ante error de integridad (varias inserciones, todo o nada)

Se quiere registrar de una sola vez a dos bailarines nuevos: "Rosa Choque" (fraternidad 1) y "Pedro Villca" (fraternidad 99, que no existe). Como es un solo lote, si uno falla no debe insertarse ninguno de los dos.

```sql
BEGIN TRY
    BEGIN TRANSACTION;

    INSERT INTO persona (nombre, ci, cargo, id_fraternidad)
    VALUES ('Rosa Choque', '8541236', 'Bailarín', 1);

    INSERT INTO persona (nombre, ci, cargo, id_fraternidad)
    VALUES ('Pedro Villca', '8541237', 'Bailarín', 99); -- fraternidad inexistente -> viola FK

    COMMIT TRANSACTION;
    PRINT 'Ambas personas registradas.';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    PRINT 'No se registró a nadie. Motivo: ' + ERROR_MESSAGE();
END CATCH;

-- Verificación: Rosa Choque NO debe existir tampoco, aunque su INSERT "sí funcionaba"
SELECT * FROM persona WHERE ci IN ('8541236','8541237');
```


Idea clave: aunque la primera inserción era válida, al fallar la FK de la segunda, el ROLLBACK deshace todo el bloque. Esa es la atomicidad.

### Ejercicio 3 — Procedimiento almacenado con transacción: inscribir una fraternidad a una edición

Se necesita un procedimiento sp_inscribir_fraternidad que reciba id_fraternidad, id_entrada y numero_participantes. Debe validar, dentro de la transacción, que esa fraternidad no tenga ya una inscripción activa en esa misma edición; si la tiene, cancela la operación con un mensaje claro.

```sql
CREATE PROCEDURE sp_inscribir_fraternidad
    @id_fraternidad INT,
    @id_entrada INT,
    @numero_participantes INT
AS
BEGIN
    SET XACT_ABORT ON;
    BEGIN TRY
        BEGIN TRANSACTION;

        IF EXISTS (
            SELECT 1 FROM inscripcion
            WHERE id_fraternidad = @id_fraternidad
              AND id_entrada = @id_entrada
              AND estado = 'activa'
        )
        BEGIN
            RAISERROR('Esa fraternidad ya tiene una inscripción activa en esta edición.', 16, 1);
        END

        INSERT INTO inscripcion (id_fraternidad, id_entrada, numero_participantes, estado)
        VALUES (@id_fraternidad, @id_entrada, @numero_participantes, 'activa');

        COMMIT TRANSACTION;
        PRINT 'Inscripción registrada correctamente.';
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        PRINT 'No se pudo inscribir: ' + ERROR_MESSAGE();
    END CATCH
END;
GO

-- Prueba: primera vez funciona
EXEC sp_inscribir_fraternidad @id_fraternidad = 1, @id_entrada = 2, @numero_participantes = 130;

-- Prueba: repetirla debe fallar (ya está activa)
EXEC sp_inscribir_fraternidad @id_fraternidad = 1, @id_entrada = 2, @numero_participantes = 130;
```

Idea clave: con SET XACT_ABORT ON, cualquier error (incluido un RAISERROR de severidad alta) aborta la transacción automáticamente, así el CATCH siempre encuentra algo coherente que revertir.

### Ejercicio 4 — Transacción multi-tabla: cambio de fraternidad de una persona con historial

Cuando un bailarín cambia de fraternidad, se debe actualizar persona.id_fraternidad y dejar registro en una tabla de historial, en la misma transacción. Si el historial no se puede insertar, el cambio de fraternidad tampoco debe quedar.

```sql
IF OBJECT_ID('dbo.historial_cambio_fraternidad', 'U') IS NULL
BEGIN
    CREATE TABLE historial_cambio_fraternidad (
        id_historial INT IDENTITY PRIMARY KEY,
        id_persona INT NOT NULL FOREIGN KEY REFERENCES persona(id_persona),
        id_fraternidad_anterior INT NOT NULL,
        id_fraternidad_nueva INT NOT NULL,
        fecha_cambio DATETIME NOT NULL DEFAULT GETDATE()
    );
END
GO

CREATE PROCEDURE sp_cambiar_fraternidad
    @id_persona INT,
    @id_fraternidad_nueva INT
AS
BEGIN
    SET XACT_ABORT ON;
    DECLARE @fraternidad_anterior INT;

    BEGIN TRY
        BEGIN TRANSACTION;

        SELECT @fraternidad_anterior = id_fraternidad
        FROM persona WHERE id_persona = @id_persona;

        IF @fraternidad_anterior IS NULL
            RAISERROR('La persona no existe.', 16, 1);

        UPDATE persona
        SET id_fraternidad = @id_fraternidad_nueva
        WHERE id_persona = @id_persona;

        INSERT INTO historial_cambio_fraternidad
            (id_persona, id_fraternidad_anterior, id_fraternidad_nueva)
        VALUES
            (@id_persona, @fraternidad_anterior, @id_fraternidad_nueva);

        COMMIT TRANSACTION;
        PRINT 'Cambio de fraternidad registrado con historial.';
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        PRINT 'Error en el cambio de fraternidad: ' + ERROR_MESSAGE();
    END CATCH
END;
GO

EXEC sp_cambiar_fraternidad @id_persona = 2, @id_fraternidad_nueva = 2;
SELECT * FROM persona WHERE id_persona = 2;
SELECT * FROM historial_cambio_fraternidad;
```

Idea clave: dos tablas, una sola transacción. O se actualiza el dato "vivo" y su historial juntos, o no se actualiza ninguno.

### Ejercicio 5 — SAVE TRANSACTION: inscripción masiva con reversión parcial

Se quiere inscribir de una vez a varias fraternidades en una edición. Si la inscripción de una fraternidad falla (por ejemplo, ya tiene una activa), no se debe cancelar el proceso completo: solo se revierte esa inscripción puntual y se sigue con las demás, dejando confirmadas las que sí funcionaron.

```sql
CREATE PROCEDURE sp_inscripcion_masiva

```

Idea clave: SAVE TRANSACTION crea un punto de retorno dentro de la transacción grande. Un ROLLBACK a ese punto no cierra la transacción, solo borra lo hecho después del SAVE.

### Ejercicio 6 Dos operaciones inseparables: cambio de presidencia (nivel: básico)

Cuando una fraternidad cambia de presidente ocurren dos cosas que van juntas:

El presidente actual pasa a cargo 'Ex-Presidente'.
Se inserta a la nueva persona con cargo 'Presidente'.
Si insertar a la nueva persona falla (por ejemplo, CI repetida), el cambio de cargo del anterior también debe deshacerse: nunca debe haber dos presidentes ni quedarse sin presidente.

```sql

```

