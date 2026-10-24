#!/bin/bash

# Configuración
CONTAINER_NAME="my-database"
DB_USER="alumno"
DB_NAME="personas-db"
BACKUP_DIR="/backups"

# Genera un prefijo de fecha y hora: AAAAMMDD_HHMMSS
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="backup_${DB_NAME}_${TIMESTAMP}.dump"

# Ejecución del respaldo dentro del contenedor
docker exec -i "$CONTAINER_NAME" pg_dump -U "$DB_USER" -d "$DB_NAME" -F c -f "${BACKUP_DIR}/${FILENAME}"

# Mensaje de confirmación en consola / logs
echo "[$(date +"%Y-%m-%d %H:%M:%S")] Respaldo completado: ${FILENAME}"