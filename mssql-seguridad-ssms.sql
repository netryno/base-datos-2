
-- Paso 1
-- En ssms
-- Crear usuario mismo privilegio que sa
CREATE LOGIN alumno_admin WITH PASSWORD = 'TuPasswordAqui123!', CHECK_POLICY = OFF;
ALTER SERVER ROLE sysadmin ADD MEMBER alumno_admin;


-- Paso 2
-- Habiliar login con password
-- TUPC\SQLEXPRESS , click derecho, propiedades, seguridad y habilitar login win y sql


-- Paso 3
-- Windows abrir> SQL Server Configuration Manager
-- Habilitar tpc
-- 'Protocols for SQLEXPRESS > tpc ip > activar 
-- Luego pestania > Ip addres, bajar hasta el final  > ip all 
TCPORT 1434

-- Paso 4 
-- reiniciar
-- En  SQL Server Configuration Manager
-- 'SQL Server (SQLEXPRESS) > restar




  SELECT * FROM departamentos where departamento_codigo = 'ia'