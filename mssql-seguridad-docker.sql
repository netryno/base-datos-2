--1.-  Abrir ssms , conectarse con estos parametros:
Server name:      localhost,1433      ← coma, no dos puntos
Authentication:   SQL Server Authentication
Login:            sa
Password:         AlumnoSql2025!

-- no olvidar
 Trust server certificate     ← obligatorio, si no da error de certificado



--2.- Ver y seleccionar la BD a utilizar
SELECT DB_NAME();        -- probablemente dice "master"
USE bd_herramientas;     -- pararte en tu BD
GO

-- una vez que estamos en la BD, lista las tablas.
SELECT name FROM sys.tables;   -- departamentos, empleados, herramientas, prestamos
GO

--3.- Crear usuarios sql server
/*
Usuario	            Permiso
admin_bd	        Control total de la BD
lector	            SELECT en todas las tablas
lector_herramientas	SELECT solo tabla herramientas
lector_empleados_nombre	SELECT solo columna empleado_nombre de empleados
*/


-- =====================================================
-- PASO 1: LOGINS (nivel servidor) — en master
-- =====================================================
USE master;
GO
IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'admin_bd')
    CREATE LOGIN admin_bd WITH PASSWORD = 'Admin#2026';

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'lector')
    CREATE LOGIN lector WITH PASSWORD = 'Lector#2026';

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'lector_herramientas')
    CREATE LOGIN lector_herramientas WITH PASSWORD = 'Herram#2026';

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = 'lector_empleados_nombre')
    CREATE LOGIN lector_empleados_nombre WITH PASSWORD = 'EmpNom#2026';
GO

-- =====================================================
-- PASO 2: USERS + PERMISOS (nivel BD) — en bd_herramientas
-- =====================================================
USE bd_herramientas;
GO

-- ---- ADMIN: control total ----
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'admin_bd')
    CREATE USER admin_bd FOR LOGIN admin_bd;
GO
IF IS_ROLEMEMBER('db_owner', 'admin_bd') = 0
    ALTER ROLE db_owner ADD MEMBER admin_bd;
GO

-- ---- LECTOR: lectura a TODAS las tablas ----
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'lector')
    CREATE USER lector FOR LOGIN lector;
GO
IF IS_ROLEMEMBER('db_datareader', 'lector') = 0
    ALTER ROLE db_datareader ADD MEMBER lector;
GO

-- ---- LECTOR SOLO HERRAMIENTAS ----
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'lector_herramientas')
    CREATE USER lector_herramientas FOR LOGIN lector_herramientas;
GO
GRANT SELECT ON dbo.herramientas TO lector_herramientas;
GO

-- ---- LECTOR SOLO COLUMNA empleado_nombre ----
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'lector_empleados_nombre')
    CREATE USER lector_empleados_nombre FOR LOGIN lector_empleados_nombre;
GO
GRANT SELECT ON dbo.empleados (empleado_nombre) TO lector_empleados_nombre;
GO

PRINT '>>> Usuarios creados correctamente';
GO


--4.- Verificar
-- ================= ADMIN: puede TODO =================
EXECUTE AS LOGIN = 'admin_bd';
    SELECT TOP 3 * FROM dbo.empleados;                       -- ✅
    INSERT INTO dbo.herramientas VALUES ('H-TEST','Pinza','nuevo');  -- ✅ (puede escribir)
    DELETE FROM dbo.herramientas WHERE codigo_inventario = 'H-TEST'; -- ✅ (limpia)
REVERT;
GO

-- ================= LECTOR: lee todo, escribe nada =================
EXECUTE AS LOGIN = 'lector';
    SELECT TOP 3 * FROM dbo.empleados;                       -- ✅
    SELECT TOP 3 * FROM dbo.herramientas;                    -- ✅
    SELECT TOP 3 * FROM dbo.prestamos;                       -- ✅
    INSERT INTO dbo.herramientas VALUES ('H-XX','Test','nuevo');  -- ❌ Msg 229
REVERT;
GO

-- ================= LECTOR HERRAMIENTAS: solo esa tabla =================
EXECUTE AS LOGIN = 'lector_herramientas';
    SELECT * FROM dbo.herramientas;                          -- ✅
    SELECT * FROM dbo.empleados;                             -- ❌ Msg 229 (SELECT denied)
    SELECT * FROM dbo.prestamos;                             -- ❌ Msg 229
REVERT;
GO

-- ================= LECTOR COLUMNA: solo empleado_nombre =================
EXECUTE AS LOGIN = 'lector_empleados_nombre';
    SELECT empleado_nombre FROM dbo.empleados;               -- ✅
    SELECT empleado_id FROM dbo.empleados;                   -- ❌ Msg 230 (columna no autorizada)
    SELECT empleado_nombre, puesto FROM dbo.empleados;       -- ❌ (incluye columna no autorizada)
    SELECT * FROM dbo.empleados;                             -- ❌
    SELECT * FROM dbo.herramientas;                          -- ❌ (tabla entera denegada)
REVERT;
GO



-- 5 otra manera de probar via ssms


Server name:      localhost,1433
Authentication:   SQL Server Authentication
Login:            lector_herramientas
Password:         Herram#2026
☑ Trust server certificate




-- 5.- eliminar usuarios

-- Orden: primero USER (en la BD), luego LOGIN (en master)
USE bd_herramientas;
GO
DROP USER IF EXISTS lector_empleados_nombre;
DROP USER IF EXISTS lector_herramientas;
DROP USER IF EXISTS lector;
DROP USER IF EXISTS admin_bd;
GO
USE master;
GO
DROP LOGIN IF EXISTS lector_empleados_nombre;
DROP LOGIN IF EXISTS lector_herramientas;
DROP LOGIN IF EXISTS lector;
DROP LOGIN IF EXISTS admin_bd;
GO