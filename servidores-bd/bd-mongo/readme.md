# Instalar con
docker compose build

# levantar docker
docker compose up

# Para iniciar ingresar Compooss
http://localhost:8081/

# con este se conecta desde Compooss
mongodb://admin:123456@mongo:27017


# Como otro ide se puede usar: MongoDB Compas
### para conectar desde alli usar:

mongodb://admin:123456@localhost:27017

# Resumen:
Dentro del navegador de Compooss: Usa mongo
En tu computadora local (Python, Compass, etc.): Usa localhost

#######################
### conectarse con table plus 
## listar personas
db.personas.find({})

db.personas.find({ "ci": "1234567" })

####################
## coneectar via consola
docker exec -it mongo-d mongosh -u admin -p 123456 --authenticationDatabase admin

# listar bases de datos
```javascript
show dbs
```

# listar colecciones
use personas
```javascript
show collections  
``` 

# listar personas
```javascript
db.personas.find().pretty()
```

# filtrar listando
```javascript
db.personas.find({ nombre: "Juan" })
```

#contar
```javascript
db.personas.countDocuments()
```

## registrar personas

```javascript
// 1) Incrementar el contador y obtener el nuevo seq
const c = db.counters.findOneAndUpdate(
  { _id: "persona_id" },
  { $inc: { seq: 1 } },
  { returnDocument: "after", upsert: true }
);
const nuevoId = c.seq;

// 2) Insertar el documento con ese id
db.personas.insertOne({
  persona_id: nuevoId,
  nombre: "Ana",
  primer_apellido: "Lopez",
  segundo_apellido: "Mira",
  ci: "1234567"
});
```

## actualizar personas
```javascript
// Actualizar por persona_id
db.personas.updateOne(
  { persona_id: 1 },
  { $set: { nombre: "Ana Maria", ci: "9999999" } }
);
```

##  elminar pesonas
```javascript
// Eliminar uno
db.personas.deleteOne({ persona_id: 1 });

// Eliminar varios
db.personas.deleteMany({ primer_apellido: "Lopez" });

// Eliminar TODOS (¡cuidado!)
db.personas.deleteMany({});
```


## Comando utiles
```javascript
show dbs                      // listar bases
show collections              // listar colecciones
db.personas.countDocuments()  // contar docs
db.personas.drop()            // borrar la colección completa
db.dropDatabase()             // borrar la base actual
exit                          // salir del shell
```