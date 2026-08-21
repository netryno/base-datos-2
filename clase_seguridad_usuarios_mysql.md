# Seguridad de Usuarios en MySQL
## Clase práctica — Base de Datos II (1h 45min)
### Escenario: SSH → contenedor Docker → servidor MySQL

---

## 0. Contexto técnico del laboratorio

```
Local (tu PC) --SSH--> Servidor remoto --docker exec--> Contenedor mysql_container --> MySQL
```

Contenedores disponibles:
- `mysql_container` (imagen `mysql`) — puerto `3306`
- `phpmyadmin_container` (imagen `phpmyadmin/phpmyadmin`) — puerto `6060`

Tablas de trabajo (adaptadas a MySQL):

```sql
CREATE DATABASE IF NOT EXISTS bd_personas;
USE bd_personas;

CREATE TABLE IF NOT EXISTS paises (
    pais_id      INT PRIMARY KEY,
    pais_nombre  VARCHAR(50) NOT NULL,
    pais_codigo  VARCHAR(5)  NOT NULL
);

CREATE TABLE IF NOT EXISTS personas (
    persona_id       INT PRIMARY KEY AUTO_INCREMENT,
    nombre           VARCHAR(50) NOT NULL,
    primer_apellido  VARCHAR(50) NOT NULL,
    segundo_apellido VARCHAR(50),
    ci               VARCHAR(20) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS viajes (
    viaje_id      INT PRIMARY KEY AUTO_INCREMENT,
    persona_id    INT NOT NULL,
    pais_id       INT NOT NULL,
    fecha_llegada DATE NOT NULL,
    FOREIGN KEY (persona_id) REFERENCES personas(persona_id) ON DELETE CASCADE,
    FOREIGN KEY (pais_id)    REFERENCES paises(pais_id)    ON DELETE CASCADE
);

CREATE INDEX idx_viajes_persona ON viajes(persona_id);
CREATE INDEX idx_viajes_pais    ON viajes(pais_id);
```

---

## 1. Conceptos clave (puntual, para pizarra)

| Concepto | Idea central |
|---|---|
| **Principio de mínimo privilegio** | Cada usuario recibe SOLO los permisos que necesita para su función, ni uno más. |
| **Usuario MySQL = `'usuario'@'host'`** | El usuario NO es solo el nombre; es el par (nombre, origen de conexión). `'lector'@'localhost'` y `'lector'@'%'` son cuentas distintas. |
| **GRANT** | Otorga privilegios (a nivel servidor, BD, tabla o columna). |
| **REVOKE** | Quita privilegios ya otorgados, sin eliminar al usuario. |
| **Roles (MySQL 8+)** | Conjuntos de privilegios reutilizables que se asignan a varios usuarios (`CREATE ROLE`). |
| **Autenticación vs Autorización** | Autenticación = "¿quién eres?" (usuario/contraseña). Autorización = "¿qué puedes hacer?" (privilegios). |
| **Control por host** | El host en `'user'@'host'` limita DESDE DÓNDE puede conectarse (IP, rango, `%` = cualquiera). Es una capa de seguridad, no solo de identidad. |
| **Least data exposure** | Se puede restringir no solo a nivel de tabla, sino a columnas específicas (`GRANT SELECT (col1, col2) ON ...`). |
| **Política de contraseñas** | Expiración, complejidad y reintentos fallidos se configuran a nivel de cuenta (`ALTER USER ... PASSWORD EXPIRE`, `FAILED_LOGIN_ATTEMPTS`). |
| **`FLUSH PRIVILEGES`** | Solo necesario si editas las tablas `mysql.*` directamente; con `GRANT`/`REVOKE`/`CREATE USER` no es obligatorio, pero es buena práctica mencionarlo. |
| **Auditoría mínima** | Registrar quién hizo qué: revisar `information_schema.USER_PRIVILEGES` y logs de conexión. |

---

## 2. Conexión: Local → SSH → Docker → MySQL

```bash
# 1) Conectar por SSH al servidor remoto
ssh usuario@IP_DEL_SERVIDOR

# 2) Verificar que el contenedor está corriendo
docker ps

# 3) Entrar al contenedor y abrir el cliente MySQL como root
docker exec -it mysql_container mysql -u root -p

# Alternativa en un solo paso (sin quedarte dentro del contenedor):
docker exec -it mysql_container mysql -u root -p -e "SELECT VERSION();"

# 4) (Opcional) Abrir una shell bash del contenedor, útil para editar archivos/logs
docker exec -it mysql_container bash
```

> Punto pedagógico: remarcar que `docker exec` NO es lo mismo que conectarse por red (`mysql -h IP -P 3306`). Aquí se entra al proceso del contenedor directamente.

---

## 3. Gestión de usuarios: admin, lector, editor

```sql
-- ===== Usuario ADMIN (control total de la BD) =====
CREATE USER 'admin_bd'@'%' IDENTIFIED BY 'AdminSeguro#2026';
GRANT ALL PRIVILEGES ON bd_personas.* TO 'admin_bd'@'%';

-- ===== Usuario LECTOR (solo SELECT, toda la BD) =====
CREATE USER 'lector'@'%' IDENTIFIED BY 'Lector#2026';
GRANT SELECT ON bd_personas.* TO 'lector'@'%';

-- ===== Usuario EDITOR (lectura + escritura, sin DDL) =====
CREATE USER 'editor'@'%' IDENTIFIED BY 'Editor#2026';
GRANT SELECT, INSERT, UPDATE, DELETE ON bd_personas.* TO 'editor'@'%';

FLUSH PRIVILEGES;
```

### Verificar privilegios otorgados

```sql
SHOW GRANTS FOR 'lector'@'%';
SHOW GRANTS FOR 'editor'@'%';
SHOW GRANTS FOR 'admin_bd'@'%';
```

---

## 4. Usuario restringido a **una sola tabla**

Caso: un usuario `consulta_viajes` que SOLO puede leer la tabla `viajes` (ni `personas` ni `paises`).

```sql
CREATE USER 'consulta_viajes'@'%' IDENTIFIED BY 'Viajes#2026';
GRANT SELECT ON bd_personas.viajes TO 'consulta_viajes'@'%';
FLUSH PRIVILEGES;
```

Prueba de aislamiento:

```sql
-- Con este usuario conectado:
SELECT * FROM viajes;      -- funciona
SELECT * FROM personas;    -- ERROR 1142 (42000): SELECT command denied
```

---

## 5. Usuario restringido a **columnas específicas** de una tabla

Caso: un usuario `rrhh_basico` que solo puede ver `nombre` y `primer_apellido` de `personas` (por ejemplo, no debe ver el `ci`, dato sensible).

```sql
CREATE USER 'rrhh_basico'@'%' IDENTIFIED BY 'Rrhh#2026';
GRANT SELECT (nombre, primer_apellido) ON bd_personas.personas TO 'rrhh_basico'@'%';
FLUSH PRIVILEGES;
```

Prueba:

```sql
SELECT nombre, primer_apellido FROM personas;   -- funciona
SELECT ci FROM personas;                        -- ERROR: columna no autorizada
SELECT * FROM personas;                         -- ERROR: incluye columnas no autorizadas
```

> Nota técnica: los privilegios a nivel columna se combinan con los de tabla. Si luego haces `GRANT SELECT ON bd_personas.personas TO 'rrhh_basico'@'%'` (sin especificar columnas), el usuario pasa a ver TODAS las columnas — hay que ser explícito y no mezclar niveles por error.

---

## 6. Revocar privilegios

```sql
-- Quitar solo el DELETE al editor (mantiene SELECT/INSERT/UPDATE)
REVOKE DELETE ON bd_personas.* FROM 'editor'@'%';

-- Quitar todos los privilegios sobre la BD (el usuario sigue existiendo, sin permisos)
REVOKE ALL PRIVILEGES ON bd_personas.* FROM 'lector'@'%';

-- Revocar el acceso a una columna específica
REVOKE SELECT (primer_apellido) ON bd_personas.personas FROM 'rrhh_basico'@'%';

-- Ver qué le queda al usuario después de revocar
SHOW GRANTS FOR 'editor'@'%';

FLUSH PRIVILEGES;
```

---

## 7. Cambio de contraseña

```sql
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
```

---

## 8. Control de acceso por origen (host / IP)

```sql
-- Solo accesible desde localhost (dentro del propio contenedor/servidor)
CREATE USER 'admin_local'@'localhost' IDENTIFIED BY 'AdminLocal#2026';

-- Solo accesible desde una IP específica
CREATE USER 'app_backend'@'192.168.1.50' IDENTIFIED BY 'Backend#2026';

-- Accesible desde un rango/subred (comodín)
CREATE USER 'oficina'@'192.168.1.%' IDENTIFIED BY 'Oficina#2026';

-- Accesible desde cualquier host (usar con mucha cautela, idealmente solo con SSL)
CREATE USER 'remoto'@'%' IDENTIFIED BY 'Remoto#2026';
```

> Punto pedagógico fuerte: `'user'@'%'` en producción es un riesgo — combinarlo siempre con contraseñas fuertes, `REQUIRE SSL`, y si es posible, restringir a rangos de IP conocidos (VPN, red interna).

```sql
-- Exigir conexión cifrada (TLS) para una cuenta
ALTER USER 'remoto'@'%' REQUIRE SSL;
```

---

## 9. Eliminar usuarios

```sql
DROP USER 'consulta_viajes'@'%';

-- Ver todos los usuarios existentes
SELECT user, host FROM mysql.user;
```

---

## 10. Lo mismo, vía phpMyAdmin (resumen rápido)

Acceder: `http://IP_DEL_SERVIDOR:6060`

| Tarea | Ruta en phpMyAdmin |
|---|---|
| Crear usuario | Pestaña **Cuentas de usuario** → **Agregar cuenta de usuario** → definir usuario, host (`%`, `localhost`, IP), contraseña |
| Asignar privilegios por BD/tabla | En **Cuentas de usuario**, clic en **Editar privilegios** del usuario → sección **Privilegios específicos de la base de datos** → elegir BD y luego tabla |
| Privilegios por columna | Dentro de **Editar privilegios** de una tabla → **Privilegios específicos de columna** → marcar columnas y el privilegio (ej. SELECT) |
| Revocar privilegios | **Editar privilegios** del usuario → desmarcar casillas → **Continuar** (equivale a REVOKE) |
| Cambiar contraseña | **Editar privilegios** → sección **Cambiar contraseña** |
| Restringir por host | Al crear/editar usuario, campo **Host** (usar IP, `%`, o `localhost`) |
| Eliminar usuario | **Cuentas de usuario** → seleccionar checkbox → **Eliminar cuentas seleccionadas** |
| Ver SQL generado | phpMyAdmin muestra el SQL antes de ejecutar (buen recurso para que el estudiante compare con el comando SQL manual) |

---

## 11. Detalles de seguridad adicionales (recomendado mencionar)

- **No usar `root` para la aplicación**: `root` solo para administración puntual, nunca como usuario de conexión del backend.
- **Nunca hardcodear contraseñas en el código**: usar variables de entorno o gestores de secretos.
- **Revisar usuarios anónimos por defecto**: en instalaciones antiguas puede existir `''@'localhost'`; eliminarlos.
- **Limitar recursos por cuenta** (previene abuso/DoS):
  ```sql
  ALTER USER 'app_backend'@'%' WITH MAX_QUERIES_PER_HOUR 1000 MAX_CONNECTIONS_PER_HOUR 100;
  ```
- **Vistas (VIEWS) como alternativa a permisos por columna**: crear una vista sin la columna sensible y dar `SELECT` solo sobre la vista, útil cuando la lógica de "columnas permitidas" es más compleja.
- **Roles en MySQL 8** para no repetir GRANTs usuario por usuario:
  ```sql
  CREATE ROLE 'rol_lector';
  GRANT SELECT ON bd_personas.* TO 'rol_lector';
  GRANT 'rol_lector' TO 'lector'@'%';
  SET DEFAULT ROLE 'rol_lector' TO 'lector'@'%';
  ```
- **Auditar accesos**: revisar `mysql.general_log` (si está activo) o el plugin `audit_log` para saber quién ejecutó qué.
- **No exponer el puerto 3306 públicamente** si no es necesario (usar SSH tunneling o red interna de Docker en vez de mapear `0.0.0.0:3306`).

---

## 12. Bonus: Backup y Restauración (mismo contenedor, otra BD)

```bash
# ===== BACKUP =====
# Generar dump de la base de datos "bd_personas" a un archivo en el HOST
docker exec mysql_container mysqldump -u root -p bd_personas > bd_personas_backup.sql

# ===== RESTAURAR EN OTRA BASE DE DATOS (mismo contenedor) =====
# 1) Crear la nueva base de datos vacía
docker exec -i mysql_container mysql -u root -p -e "CREATE DATABASE bd_personas_restaurada;"

# 2) Restaurar el dump dentro de la nueva base de datos
docker exec -i mysql_container mysql -u root -p bd_personas_restaurada < bd_personas_backup.sql

# ===== VERIFICAR =====
docker exec -it mysql_container mysql -u root -p -e "USE bd_personas_restaurada; SHOW TABLES; SELECT COUNT(*) FROM personas;"
```

> Nota práctica: `mysqldump` requiere que el archivo de salida (`>`) se maneje en el HOST (no dentro del contenedor), por eso no se usa `-it`, solo `docker exec` sin TTY interactivo para el paso de backup.

Variante — backup comprimido (recomendado si la BD crece):

```bash
docker exec mysql_container mysqldump -u root -p bd_personas | gzip > bd_personas_backup.sql.gz

# Restaurar desde comprimido
gunzip < bd_personas_backup.sql.gz | docker exec -i mysql_container mysql -u root -p bd_personas_restaurada
```

---

## 13. Cierre de clase — checklist de repaso (5 min)

- [ ] Crear usuario con `CREATE USER`
- [ ] Diferenciar `'user'@'localhost'` vs `'user'@'%'`
- [ ] Otorgar privilegios a nivel BD, tabla y columna
- [ ] `REVOKE` sin eliminar la cuenta
- [ ] Cambiar y forzar expiración de contraseña
- [ ] Restringir por host/IP
- [ ] Replicar todo en phpMyAdmin
- [ ] Backup con `mysqldump` y restauración en BD distinta
