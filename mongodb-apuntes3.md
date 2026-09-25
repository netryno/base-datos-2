# Clase: Introducción práctica a MongoDB con mongosh

Base de datos usada en todos los ejemplos: **biblioteca** (colecciones `libros`, `usuarios`, `prestamos`). Es un dominio que cualquier estudiante entiende sin explicación adicional, y permite mostrar relaciones (préstamo liga un libro con un usuario) sin salir de NoSQL.

Entorno de referencia: Mongo 7 corriendo en Docker (`mongo:7`, puerto 27017 expuesto), tal como lo tienes ahora mismo.

---

## 1. Conexión a MongoDB

### 1.1 Conexión al contenedor Docker (dos formas)

**A) mongosh instalado en el host, apuntando al puerto expuesto** (lo que ya te funciona):
```bash
mongosh "mongodb://127.0.0.1:27017"
```

**B) mongosh dentro del propio contenedor** (útil si el host no tiene mongosh instalado):
```bash
docker exec -it mongo-d mongosh

# Credenciales revisar en docker-compose.yml.. 
docker exec -it mongo-d mongosh -u admin -p 123456 --authenticationDatabase admin
```
`mongo-d` es el nombre/hash del contenedor (`docker ps` lo confirma).

Diferencia a remarcar en clase: en (A) el cliente vive en tu máquina y solo el servidor está en Docker; en (B) cliente y servidor viven en el mismo contenedor. El resultado de conexión es idéntico.

### 1.2 Conexión a MongoDB Atlas (nube)

Desde el panel de Atlas: **Connect → Drivers/Shell** se obtiene una cadena como:
```bash
mongosh "mongodb+srv://cluster0.xxxxx.mongodb.net/" --apiVersion 1 --username miUsuario

# personalizar usuario y pedira contraseña (si no se recuerda cambiar en mongo atlas)
mongosh "mongodb+srv://cluster0.yscofqp.mongodb.net/" --apiVersion 1 --username pcaihuara_db_user
```
Pide la contraseña de forma interactiva. Puntos a marcar:
- `mongodb://` = conexión directa a un nodo (como en Docker local).
- `mongodb+srv://` = descubrimiento automático de todos los nodos del clúster (replica set), usado por Atlas.
- Atlas exige usuario/contraseña y **IP en whitelist** (Network Access); Docker local no exige nada de eso por defecto.

### 1.3 Verificar la conexión activa (con que user estoy conectado)
```js
db.runCommand({ connectionStatus: 1 })
```

---

## 2. Comandos básicos de navegación

| Comando | Qué hace |
|---|---|
| `show dbs` | Lista las bases de datos existentes |
| `use biblioteca` | Cambia (o crea) a la base `biblioteca` |
| `db` | Muestra la base activa |
| `show collections` | Lista las colecciones de la base activa |
| `db.libros.help()` | Ayuda de métodos disponibles para esa colección |
| `db.stats()` | Estadísticas de la base activa (tamaño, colecciones, índices) |
| `db.libros.countDocuments()` | Cantidad de documentos en la colección |
| `cls` | Limpia la pantalla |
| `exit` | Salir de mongosh |

Nota importante para el alumno: `use biblioteca` **no crea nada todavía**. Mongo crea la base y la colección recién cuando se inserta el primer documento.

---

## 3. Base de datos, colecciones y documentos

Comparación rápida con lo que ya conocen de SQL:

| Relacional (SQL) | MongoDB |
|---|---|
| Base de datos | Base de datos |
| Tabla | Colección |
| Fila / registro | Documento |
| Columna | Campo |
| Esquema fijo (DDL) | Esquema flexible (cada documento puede variar) |

Ejemplo de un documento de la colección `libros`:
```js
{
  _id: ObjectId("6710a1..."),
  titulo: "Cien años de soledad",
  autor: "Gabriel García Márquez",
  anio: 1967,
  genero: "Realismo mágico",
  disponible: true,
  copias: 3
}
```

Punto importante: `_id` es obligatorio y único; si no lo defines, Mongo genera un `ObjectId` automáticamente. Otro punto clave: dos documentos de la misma colección pueden tener campos distintos (a diferencia de una tabla SQL, donde todas las filas comparten columnas). Ejemplo para mostrar en vivo:
```js
db.libros.insertOne({ titulo: "Rayuela", autor: "Julio Cortázar" })
db.libros.insertOne({ titulo: "1984", autor: "George Orwell", anio: 1949, coleccion_especial: true })
```
Ambos son válidos en la misma colección, aunque el segundo tiene un campo que el primero no tiene.

Para verificar los datos insertados:
```js
 db.libros.find()
```
---

## 4. CRUD básico

### Create
```js
// Un documento
db.libros.insertOne({
  titulo: "El Aleph", autor: "Jorge Luis Borges", anio: 1949, genero: "Cuento", disponible: true, copias: 2
})

// Varios documentos
db.libros.insertMany([
  { titulo: "Ficciones", autor: "Jorge Luis Borges", anio: 1944, disponible: true, copias: 1 },
  { titulo: "Pedro Páramo", autor: "Juan Rulfo", anio: 1955, disponible: false, copias: 0 }
])
```

### Read
```js
db.libros.find()                          // todos los documentos
db.libros.find().pretty()                 // salida formateada (mongosh la formatea igual por defecto)
db.libros.findOne({ titulo: "1984" })      // un solo documento
db.libros.find({}, { titulo: 1, autor: 1, _id: 0 })   // proyección: solo estos campos
```

### Update
```js
// Modifica un campo de un documento
db.libros.updateOne(
  { titulo: "Pedro Páramo" },
  { $set: { disponible: true, copias: 2 } }
)

// Modifica varios documentos que cumplen la condición
db.libros.updateMany(
  { genero: "Cuento" },
  { $set: { destacado: true } }
)

// Reemplaza el documento completo (cuidado: borra los campos no incluidos)
db.libros.replaceOne(
  { titulo: "Rayuela" },
  { titulo: "Rayuela", autor: "Julio Cortázar", anio: 1963, disponible: true, copias: 1 }
)
```

### Delete
```js
db.libros.deleteOne({ titulo: "Ficciones" })
db.libros.deleteMany({ disponible: false })
```

Ejercicio corto sugerido en vivo: pedir a un alumno que inserte un libro, a otro que lo busque, a otro que lo actualice y a otro que lo borre. Se ve el ciclo completo en 4 comandos.

---

## 5. Scripts de carga inicial (datos de ejemplo)

Pensados para pegar directo en mongosh y tener datos con los que trabajar el resto de la clase.

```js
use biblioteca

db.libros.insertMany([
  { titulo: "Cien años de soledad", autor: "Gabriel García Márquez", anio: 1967, genero: "Realismo mágico", disponible: true, copias: 3 },
  { titulo: "1984", autor: "George Orwell", anio: 1949, genero: "Distopía", disponible: true, copias: 5 },
  { titulo: "El principito", autor: "Antoine de Saint-Exupéry", anio: 1943, genero: "Fábula", disponible: true, copias: 4 },
  { titulo: "Crimen y castigo", autor: "Fiódor Dostoyevski", anio: 1866, genero: "Drama", disponible: false, copias: 0 },
  { titulo: "Don Quijote de la Mancha", autor: "Miguel de Cervantes", anio: 1605, genero: "Clásico", disponible: true, copias: 2 },
  { titulo: "Rayuela", autor: "Julio Cortázar", anio: 1963, genero: "Experimental", disponible: true, copias: 1 },
  { titulo: "La sombra del viento", autor: "Carlos Ruiz Zafón", anio: 2001, genero: "Misterio", disponible: true, copias: 3 },
  { titulo: "Fahrenheit 451", autor: "Ray Bradbury", anio: 1953, genero: "Ciencia ficción", disponible: false, copias: 0 },
  { titulo: "Orgullo y prejuicio", autor: "Jane Austen", anio: 1813, genero: "Romance", disponible: true, copias: 2 },
  { titulo: "El Aleph", autor: "Jorge Luis Borges", anio: 1949, genero: "Cuento", disponible: true, copias: 2 }
])

db.usuarios.insertMany([
  { nombre: "Ana Rojas", email: "ana.rojas@mail.com", tipo: "estudiante", activo: true },
  { nombre: "Luis Mamani", email: "luis.mamani@mail.com", tipo: "docente", activo: true },
  { nombre: "Carla Vega", email: "carla.vega@mail.com", tipo: "estudiante", activo: true },
  { nombre: "Jorge Flores", email: "jorge.flores@mail.com", tipo: "estudiante", activo: false },
  { nombre: "Marisol Paz", email: "marisol.paz@mail.com", tipo: "docente", activo: true }
])

db.prestamos.insertMany([
  { libro: "1984", usuario: "Ana Rojas", fecha_prestamo: new Date("2026-08-01"), devuelto: false },
  { libro: "Crimen y castigo", usuario: "Luis Mamani", fecha_prestamo: new Date("2026-07-15"), devuelto: false },
  { libro: "Fahrenheit 451", usuario: "Carla Vega", fecha_prestamo: new Date("2026-07-20"), devuelto: true }
])
```

Verificación rápida tras la carga:
```js
db.libros.countDocuments()     // 10
db.usuarios.countDocuments()   // 5
db.prestamos.countDocuments()  // 3
```

---

## 6. Filtros: de básico a avanzado

### Nivel básico — igualdad simple
```js
db.libros.find({ genero: "Cuento" })
db.libros.find({ disponible: true })
```

### Nivel intermedio — operadores de comparación y lógicos

| Operador | Significado | Ejemplo |
|---|---|---|
| `$gt` / `$gte` | mayor que / mayor o igual | `{ anio: { $gt: 1950 } }` |
| `$lt` / `$lte` | menor que / menor o igual | `{ anio: { $lt: 1900 } }` |
| `$ne` | distinto de | `{ genero: { $ne: "Romance" } }` |
| `$in` | dentro de una lista | `{ genero: { $in: ["Cuento", "Fábula"] } }` |
| `$and` / `$or` | combinar condiciones | ver abajo |
| `$regex` | coincidencia de texto (patrón) | `{ titulo: { $regex: "^El" } }` |

Ejemplos ejecutables:
```js
// Libros publicados después de 1950 y disponibles
db.libros.find({ anio: { $gt: 1950 }, disponible: true })

// Libros de género Cuento o Fábula
db.libros.find({ genero: { $in: ["Cuento", "Fábula"] } })

// disponible=false O copias=0 (con $or explícito)
db.libros.find({ $or: [ { disponible: false }, { copias: 0 } ] })

// Título que empieza con "El" (case-insensitive)
db.libros.find({ titulo: { $regex: "^El", $options: "i" } })
```

Explicar en clase: cuando pones varios campos separados por coma dentro de un mismo `find({...})`, Mongo los trata como `AND` implícito — por eso el primer ejemplo no necesita `$and` explícito.

### Nivel avanzado (pero comprensible) — pipeline de agregación

La agregación es una **secuencia de pasos** (`$match` filtra, `$group` agrupa, `$sort` ordena, `$project` elige campos). Se explica como una tubería: cada etapa recibe la salida de la anterior.

```js
// Cantidad de libros disponibles por género, ordenado de mayor a menor
db.libros.aggregate([
  { $match: { disponible: true } },
  { $group: { _id: "$genero", total: { $sum: 1 } } },
  { $sort: { total: -1 } }
])
```

```js
// $lookup: traer, para cada préstamo, los datos del libro relacionado (equivalente a un JOIN)
db.prestamos.aggregate([
  {
    $lookup: {
      from: "libros",
      localField: "libro",
      foreignField: "titulo",
      as: "info_libro"
    }
  }
])
```
Este último es el mejor momento para conectar con lo que ya saben de SQL: `$lookup` es, conceptualmente, un `LEFT JOIN`.

---

## 7. Seguridad: usuarios y roles

Los usuarios de administración se crean sobre la base `admin`.

```js
use admin

// Listar usuarios existentes
db.getUsers()

// Crear un usuario administrador
db.createUser({
  user: "admin_bd2",
  pwd: "ClaveSegura123",
  roles: [ { role: "userAdmin", db: "admin" }, { role: "readWrite", db: "biblioteca" } ]
})
```

Crear un usuario con acceso limitado, solo a la base `biblioteca`:
```js
use biblioteca

db.createUser({
  user: "lector_app",
  pwd: "Clave2026",
  roles: [ { role: "read", db: "biblioteca" } ]   // solo lectura
})
```

Roles predefinidos más comunes (tabla para pizarra):

| Rol | Alcance |
|---|---|
| `read` | Solo lectura sobre la base indicada |
| `readWrite` | Lectura y escritura |
| `dbAdmin` | Tareas administrativas (índices, estadísticas), sin acceso a datos |
| `userAdmin` | Crear/eliminar usuarios y roles de esa base |
| `root` | Superusuario (solo en `admin`) |

Cambiar nivel de acceso (subir o bajar rol) sin recrear el usuario:
```js
// Dar de alta un rol adicional
db.grantRolesToUser("lector_app", [ { role: "readWrite", db: "biblioteca" } ])

// Dar de baja un rol
db.revokeRolesFromUser("lector_app", [ { role: "readWrite", db: "biblioteca" } ])
```

Eliminar un usuario:
```js
db.dropUser("lector_app")
```

Nota para mencionar: el contenedor Docker que están usando probablemente corre **sin autenticación activada** (`--auth`). Vale la pena mostrar en vivo cómo se activaría (`mongod --auth` o la variable `MONGO_INITDB_ROOT_USERNAME` en el `docker run`), aunque no se practique en el laboratorio.

---

## 8. Backup y restore

Ambas herramientas se ejecutan **desde la terminal del sistema, no desde mongosh**.

### Backup con mongodump
```bash
# Backup de toda la instancia, ejecutado dentro del contenedor
docker exec mongo-d mongodump --out /data/backup

# Backup de una sola base
docker exec mongo-d mongodump --db biblioteca --out /data/backup

# Sacar el backup del contenedor hacia el host
docker cp mongo-d:/data/backup ./backup-biblioteca
```
`mongodump` genera archivos `.bson` (los datos) y `.json` (metadatos/índices) por cada colección.

### Restore con mongorestore
```bash
# Restaurar una base completa desde el backup
docker exec mongo-d mongorestore --db biblioteca /data/backup/biblioteca

# Restaurar sobreescribiendo lo existente
docker exec mongo-d mongorestore --db biblioteca --drop /data/backup/biblioteca
```

Ejercicio de cierre sugerido: hacer `mongodump` de `biblioteca`, borrar la colección `libros` completa (`db.libros.drop()`), y luego restaurarla con `mongorestore` para comprobar que los 10 documentos vuelven exactamente igual.

---

## Cierre de la clase

Secuencia recomendada para la sesión en vivo: 1→2→3 (contexto, 15 min) → 4→5 (práctica CRUD, 25 min) → 6 (filtros, 25 min) → 7→8 (seguridad y backup, 20 min). Los scripts de la sección 5 dejan la base lista para que las secciones 6, 7 y 8 se practiquen sin tiempo perdido cargando datos.
