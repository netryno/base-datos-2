-- ---------------------------------------------------------------------------------------------------------------------
--                             Conectarse a mysql                    
-- ---------------------------------------------------------------------------------------------------------------------

#Ingresar al docker (mysql)

docker exec -it mysql_container sh

#de ahi recin al mysql
mysql -u root -p

#contraseña: 
URL: http://localhost:6060
Server: mysql
Username: root or dbuser
Password: setrootpassword or dbpassword



#Ingresar directo al mysql del docker
docker exec -it mysql_container mysql -u root -p



-- ===== Bases de datos =====
SHOW DATABASES;
USE bd_personas;
SELECT DATABASE();          -- ver en qué BD estás parado


-- ===== Tablas =====
SHOW TABLES;
DESCRIBE personas;          -- estructura de una tabla (columnas, tipos, llaves)
SHOW CREATE TABLE personas; -- el DDL completo (constraints, FKs, etc.)
SHOW INDEX FROM viajes;     -- ver índices de una tabla


-- ===== Usuarios =====
SELECT user, host FROM mysql.user;   -- listar todos los usuarios y su host
SHOW GRANTS FOR 'editor'@'%';        -- ver privilegios de un usuario
SELECT CURRENT_USER();               -- ver con qué usuario estás conectado ahora

-- ===== Procesos / conexiones activas =====
SHOW PROCESSLIST;            -- quién está conectado y qué está ejecutando
SHOW STATUS LIKE 'Threads_connected';

-- ===== Info del servidor =====
SELECT VERSION();
STATUS;                      -- resumen completo (versión, uptime, charset, etc.)
SHOW VARIABLES LIKE 'max_connections';

-- ===== Datos rápidos =====
SELECT COUNT(*) FROM personas;
SELECT * FROM personas LIMIT 5;

-- ---------------------------------------------------------------------------------------------------------------------
--                              Gestión de usuarios: admin, lector, editor                   
-- ---------------------------------------------------------------------------------------------------------------------
-- ===== Usuario ADMIN (control total de la BD) =====
CREATE USER 'admin_bd'@'%' IDENTIFIED BY 'AdminSeguro#2026';
GRANT ALL PRIVILEGES ON bd_personas.* TO 'admin_bd'@'%';

-- ===== Usuario LECTOR (solo SELECT, toda la BD) =====
CREATE USER 'lector'@'%' IDENTIFIED BY 'Lector#2026';
GRANT SELECT ON bd_personas.* TO 'lector'@'%';

-- ===== Usuario EDITOR (lectura + escritura, sin DDL) =====
CREATE USER 'editor'@'%' IDENTIFIED BY 'Editor#2026';
GRANT SELECT, INSERT, UPDATE, DELETE ON bd_personas.* TO 'editor'@'%';

-- ===== Usuario lector de solo paises =====
CREATE USER 'lector_paises'@'%' IDENTIFIED BY 'Paises#2026';
GRANT SELECT ON bd_personas.paises TO 'lector_paises'@'%';
-- probar conectandose con ese usuario en pypmyadmin

FLUSH PRIVILEGES;



-- Ver privilegios de los usuarios creados
SHOW GRANTS FOR 'lector'@'%';
SHOW GRANTS FOR 'editor'@'%';
SHOW GRANTS FOR 'admin_bd'@'%';


-- Usuario restringido a una sola tabla

CREATE USER 'consulta_viajes'@'%' IDENTIFIED BY 'Viajes#2026';
GRANT SELECT ON bd_personas.viajes TO 'consulta_viajes'@'%';
FLUSH PRIVILEGES;



--- Usuario restringido a columnas específicas de una tabla

CREATE USER 'rrhh_basico'@'%' IDENTIFIED BY 'Rrhh#2026';
GRANT SELECT (nombre, primer_apellido) ON bd_personas.personas TO 'rrhh_basico'@'%';
FLUSH PRIVILEGES;

SELECT nombre, primer_apellido FROM personas;   -- funciona
SELECT ci FROM personas;                        -- ERROR: columna no autorizada
SELECT * FROM personas;                         -- ERROR: incluye columnas no autorizadas



-- ---------------------------------------------------------------------------------------------------------------------
--                              Revocar privilegios            
-- ---------------------------------------------------------------------------------------------------------------------



-- Quitar solo el DELETE al editor (mantiene SELECT/INSERT/UPDATE)
REVOKE DELETE ON bd_personas.* FROM 'editor'@'%';

-- ver detalles de user
SHOW GRANTS FOR 'editor'@'%';

-- Quitar todos los privilegios sobre la BD (el usuario sigue existiendo, sin permisos)
REVOKE ALL PRIVILEGES ON bd_personas.* FROM 'lector'@'%';

-- Revocar el acceso a una columna específica
REVOKE SELECT (primer_apellido) ON bd_personas.personas FROM 'rrhh_basico'@'%';

-- Ver qué le queda al usuario después de revocar
SHOW GRANTS FOR 'editor'@'%';

FLUSH PRIVILEGES;


-- ---------------------------------------------------------------------------------------------------------------------
--                              Cambio de contraseña          
-- ---------------------------------------------------------------------------------------------------------------------
-- Forma moderna recomendada (MySQL 5.7.6+/8.x)
ALTER USER 'editor'@'%' IDENTIFIED BY 'NuevaClave#2027';

-- Forzar cambio de contraseña en el próximo login
ALTER USER 'editor'@'%' PASSWORD EXPIRE;

-- Política de expiración automática cada 90 días
ALTER USER 'editor'@'%' PASSWORD EXPIRE INTERVAL 90 DAY;

-- Bloquear cuenta tras intentos fallidos (MySQL 8.0.19+)
ALTER USER 'editor'@'%' FAILED_LOGIN_ATTEMPTS 3 PASSWORD_LOCK_TIME 1;

-- Bloquear/desbloquear una cuenta manualmente
ALTER USER 'editor'@'%' ACCOUNT LOCK;
ALTER USER 'editor'@'%' ACCOUNT UNLOCK;

-- ---------------------------------------------------------------------------------------------------------------------
--                            Control de acceso por origen (host / IP)        
-- ---------------------------------------------------------------------------------------------------------------------


-- Solo accesible desde localhost (dentro del propio contenedor/servidor)
CREATE USER 'admin_local'@'localhost' IDENTIFIED BY 'AdminLocal#2026';

-- Solo accesible desde una IP específica
CREATE USER 'app_backend'@'192.168.1.50' IDENTIFIED BY 'Backend#2026';

-- Accesible desde un rango/subred (comodín)
CREATE USER 'oficina'@'192.168.1.%' IDENTIFIED BY 'Oficina#2026';

-- Accesible desde cualquier host (usar con mucha cautela, idealmente solo con SSL)
CREATE USER 'remoto'@'%' IDENTIFIED BY 'Remoto#2026';


-- ---------------------------------------------------------------------------------------------------------------------
--                            elminar usuarios
-- ---------------------------------------------------------------------------------------------------------------------
DROP USER 'editor'@'%';

-- Ver todos los usuarios existentes
SELECT user, host FROM mysql.user;



-- ---------------------------------------------------------------------------------------------------------------------
--                           backup
-- ---------------------------------------------------------------------------------------------------------------------
--tarea .. sacar backup y restarurrlo en otra bdd