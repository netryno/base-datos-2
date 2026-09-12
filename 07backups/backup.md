## Crea un archivo llamado backup.sh en el directorio de tu proyecto y dale permisos de ejecución.

## Permisos de ejecución (Mac y Linux):

## Bash
chmod +x backup.sh

## Verificación: Ejecútalo manualmente con ./backup.sh y revisa la carpeta ./backups en tu máquina local.
./backup.sh


## Configuración en Crontab (Mac / Linux)
### Para editar las tareas programadas de tu usuario, abre el editor de cron


## Bash
crontab -e



# ------------------------------------------------------------------------------
# TAREA 2: Respaldo cada minuto 
# ------------------------------------------------------------------------------
## 1. Para probarlo cada minuto:


## 2. Para ejecutarlo cada medianoche (00:00):
# ------------------------------------------------------------------------------
# TAREA 2: Respaldo diario a la medianoche (Modo Producción - Desactivado por ahora)
# ------------------------------------------------------------------------------