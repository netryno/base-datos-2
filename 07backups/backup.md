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
#### * * * * * /ruta/absoluta/a/tu/proyecto/backup.sh >> /ruta/absoluta/a/tu/proyecto/backup.log 2>&1

## cada minuto
* * * * * /Volumes/orico/desarrollo/cato/base-datos-2/07backups/backup.sh >> /Volumes/orico/desarrollo/cato/base-datos-2/07backups/copias/backup.log 2>&1



## 2. Para ejecutarlo cada medianoche (00:00):
# ------------------------------------------------------------------------------
# TAREA 2: Respaldo diario a la medianoche (Modo Producción - Desactivado por ahora)
# ------------------------------------------------------------------------------