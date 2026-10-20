# Sistema Académico · Python + MongoDB

Aplicación monolítica de ejemplo para la materia Base de Datos II. Permite
registrar **alumnos**, registrar **asignaturas** y **matricular** alumnos en
una asignatura, trabajando directamente con documentos MongoDB mediante
PyMongo (sin ORM/ODM).

## Estructura

```
app.py                Conexión, esquema de colecciones y rutas web (todo el código Python)
templates/            Vistas HTML: base, inicio, alumnos, asignaturas, matricula
static/estilo.css     Hoja de estilos
requirements.txt      Dependencias: flask, pymongo, python-dotenv
Dockerfile            Imagen de la aplicación
docker-compose.yml    Servicio web conectado a la red del contenedor MongoDB
.env                  Configuración (URI de MongoDB, puerto, red Docker)
```

## Puesta en marcha

1. Tener un MongoDB corriendo en Docker (por ejemplo el proyecto `bd-mongo`).
2. Revisar `.env`: `MONGO_URI`, `DB_NAME`, `DOCKER_MONGO_NETWORK` y `APP_PORT`.
3. Construir y levantar:

```bash
docker compose build
docker compose up
```

4. Abrir <http://localhost:8076>.

Al arrancar, la aplicación espera a MongoDB, crea la base de datos y las
colecciones `alumno` y `asignatura` **si no existen** (con el mismo
`$jsonSchema` del script del shell) y crea los índices únicos.

Si MongoDB corre fuera de Docker, usar por ejemplo
`MONGO_URI=mongodb://host.docker.internal:27017` y cualquier red existente.

## Modelo de datos

| Colección    | Contenido                                                                 |
|--------------|---------------------------------------------------------------------------|
| `alumno`     | `{ dni, nombre, edad }` — índice único en `dni`.                           |
| `asignatura` | `{ gestion, codigo, nombre, descripcion, profesor: {…}, inscritos: […] }` — índice único en `(gestion, codigo)`. |

`profesor` es un documento **embebido**; `inscritos` es un arreglo de
`{ alumno_id, fecha_inscripcion }` que **referencia** al `_id` del alumno.

## Operaciones MongoDB empleadas

| Acción                     | Comando                                                                 |
|----------------------------|-------------------------------------------------------------------------|
| Crear colección            | `db.createCollection(nombre, { validator: { $jsonSchema }, … })`        |
| Índice único               | `db.alumno.createIndex({ dni: 1 }, { unique: true })`                   |
| Registrar                  | `insertOne(documento)`                                                  |
| Listar                     | `find().sort()`                                                         |
| Matricular (sin duplicar)  | `updateOne({ _id, "inscritos.alumno_id": { $ne } }, { $push: … })`      |
| Retirar                    | `updateOne({ _id }, { $pull: { inscritos: { alumno_id } } })`           |
| Inscritos + datos alumno   | `aggregate([ $match, $unwind, $lookup, $unwind, $project, $sort ])`     |

MongoDB no tiene claves foráneas: la aplicación verifica que el alumno exista
antes de insertarlo en `inscritos`.
