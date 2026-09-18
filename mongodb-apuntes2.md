# MongoDB Atlas
> Es una base de datos en la nube totalmente administrada que maneja toda la complejidad de la implementación, la administración y la reparación de sus implementaciones en el proveedor de servicios en la nube de su elección

### Introducción a MongoDB Atlas
- Crear una cuenta de MongoDB Cloud
- Creación de un clúster de MongoDB Atlas
- Configurar el acceso a la red y crear un usuario de clúster
- Conéctese al clúster

> No requiere tarjeta, la capa gratuita de MongoDB Atlas ofrece un clúster de 
512 MB de almacenamiento, 
con un máximo de 100 conexiones simultáneas 
y 100.000 operaciones por mes.

## 1.- Registro
https://www.mongodb.com/cloud/atlas/register

- https://account.mongodb.com/account/login
- Login con google, aceptar términos y condiciones, crear cuenta.
- Aceptar privacy y términos de servicio.
- (se traba, por algun detalle se crear un ciclico ahi)
- Ingresando al email y cambiando contraseña, se puede continuar con el registro.
- Completar profile info.

## 2 - Crear un cluster en MongoDB Atlas
- Ir a: https://cloud.mongodb.com
- Comenzar, create cluster, free tier, elegir proveedor y región, crear cluster.
- Click "create deployment", esperar a que se cree el cluster.


## 3 - Crear Usuario de Base de Datos
- Connect to Cluster0
pcaihuara_db_user
asdfasdfasdf

- Seleccionar , metodo de acceso, compass, copiar string de conexión, cambiar contraseña a algo más seguro, por ejemplo:

mongodb+srv://<usuario>:<contraseña>@cluster...)
mongodb+srv://pcaihuara_db_user:asdfasdfasdf@cluster0.yscofqp.mongodb.net/


- Verificar version, si no la ultima compatible con compass.
- click done,


## 4 - Configurar Acceso de Red (IP)
- database access, network access, ip acces list: (añadir ip publica)

## 5 - Conectarse desde Compass
- Abrir Compass, pegar string de conexió



# Concion con consola:
- Project overview,

mongosh "mongodb+srv://cluster0.yscofqp.mongodb.net/" --apiVersion 1 --username <db_username>

mongosh "mongodb+srv://cluster0.yscofqp.mongodb.net/" --apiVersion 1 --username pcaihuara_db_user
- Se conecta via consola y se puede realizar operaciones de base de datos, por ejemplo:
show dbs
use <db_name>
show collections









