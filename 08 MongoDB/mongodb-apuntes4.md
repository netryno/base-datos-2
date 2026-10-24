# Modelado de Base de Datos NoSQL con MongoDB

Este documento presenta dos enfoques fundamentales para el modelado de datos en MongoDB (Referenciado y Embebido), utilizando un caso práctico de **Profesores, Cursos y Alumnos**.

---

## Opción 1: Modelado Referenciado (Normalizado)
Ideal cuando los datos cambian constantemente. Utiliza referencias por IDs para conectar los documentos de distintas colecciones, evitando la duplicidad de información.

### Colección: `profesores`
```json
[
  {
    "_id": {"$oid": "60d5ec49f123456789abcdef"},
    "nombre": "Carlos Mendoza",
    "email": "carlos.mendoza@email.com",
    "especialidad": "Desarrollo Backend"
  },
  {
    "_id": {"$oid": "60d5ec49f123456789abcde0"},
    "nombre": "Ana Rodríguez",
    "email": "ana.rodriguez@email.com",
    "especialidad": "Bases de Datos NoSQL"
  },
  {
    "_id": {"$oid": "60d5ec49f123456789abcde1"},
    "nombre": "Luis Gómez",
    "email": "luis.gomez@email.com",
    "especialidad": "Inteligencia Artificial"
  }
]
```

### Colección: `cursos`
```json
[
  {
    "_id": 1,
    "nombre": "Node.js Avanzado",
    "descripcion": "Curso profundo de microservicios con Node.js",
    "credito": 5,
    "profesor_id": {"$oid": "60d5ec49f123456789abcdef"},
    "alumnos_inscritos": [101, 102]
  },
  {
    "_id": 2,
    "nombre": "Master en MongoDB",
    "descripcion": "Modelado y optimización en bases de datos documentales",
    "credito": 4,
    "profesor_id": {"$oid": "60d5ec49f123456789abcde0"},
    "alumnos_inscritos": [101, 103]
  },
  {
    "_id": 3,
    "nombre": "Introducción a Python",
    "descripcion": "Fundamentos de programación y análisis de datos",
    "credito": 3,
    "profesor_id": {"$oid": "60d5ec49f123456789abcde1"},
    "alumnos_inscritos": [102, 103]
  }
]
```

### Colección: `alumnos`
```json
[
  {
    "_id": 101,
    "nombre": "Sofía Martínez",
    "email": "sofia.m@email.com",
    "telefono": "+59171234567",
    "cursos_inscritos": [1, 2]
  },
  {
    "_id": 102,
    "nombre": "Alejandro Silva",
    "email": "ale.silva@email.com",
    "telefono": "+59172345678",
    "cursos_inscritos": [1, 3]
  },
  {
    "_id": 103,
    "nombre": "Lucía Fernández",
    "email": "lucia.f@email.com",
    "telefono": "+59173456789",
    "cursos_inscritos": [2, 3]
  }
]
```

---

## Opción 2: Modelado Embebido (Denormalizado)
Aprovecha la naturaleza de MongoDB guardando documentos dentro de otros. Es excelente para lecturas veloces ya que evita operaciones de unión (JOINs) en el servidor.

### Colección: `profesores`
```json
[
  {
    "_id": {"$oid": "60d5ec49f123456789abcdef"},
    "nombre": "Carlos Mendoza",
    "email": "carlos.mendoza@email.com",
    "especialidad": "Desarrollo Backend"
  },
  {
    "_id": {"$oid": "60d5ec49f123456789abcde0"},
    "nombre": "Ana Rodríguez",
    "email": "ana.rodriguez@email.com",
    "especialidad": "Bases de Datos NoSQL"
  },
  {
    "_id": {"$oid": "60d5ec49f123456789abcde1"},
    "nombre": "Luis Gómez",
    "email": "luis.gomez@email.com",
    "especialidad": "Inteligencia Artificial"
  }
]
```

### Colección: `cursos`
```json
[
  {
    "_id": 1,
    "nombre": "Node.js Avanzado",
    "descripcion": "Curso profundo de microservicios con Node.js",
    "credito": 5,
    "profesor": {
      "nombre": "Carlos Mendoza",
      "especialidad": "Desarrollo Backend"
    },
    "alumnos_inscritos": [
      { "nombre": "Sofía Martínez", "email": "sofia.m@email.com" },
      { "nombre": "Alejandro Silva", "email": "ale.silva@email.com" }
    ]
  },
  {
    "_id": 2,
    "nombre": "Master en MongoDB",
    "descripcion": "Modelado y optimización en bases de datos documentales",
    "credito": 4,
    "profesor": {
      "nombre": "Ana Rodríguez",
      "especialidad": "Bases de Datos NoSQL"
    },
    "alumnos_inscritos": [
      { "nombre": "Sofía Martínez", "email": "sofia.m@email.com" },
      { "nombre": "Lucía Fernández", "email": "lucia.f@email.com" }
    ]
  },
  {
    "_id": 3,
    "nombre": "Introducción a Python",
    "descripcion": "Fundamentos de programación y análisis de datos",
    "credito": 3,
    "profesor": {
      "nombre": "Luis Gómez",
      "especialidad": "Inteligencia Artificial"
    },
    "alumnos_inscritos": [
      { "nombre": "Alejandro Silva", "email": "ale.silva@email.com" },
      { "nombre": "Lucía Fernández", "email": "lucia.f@email.com" }
    ]
  }
]
```

### Colección: `alumnos`
```json
[
  {
    "nombre": "Sofía Martínez",
    "email": "sofia.m@email.com",
    "telefono": "+59171234567",
    "cursos_inscritos": [
      { "nombre": "Node.js Avanzado", "credito": 5 },
      { "nombre": "Master en MongoDB", "credito": 4 }
    ]
  },
  {
    "nombre": "Alejandro Silva",
    "email": "ale.silva@email.com",
    "telefono": "+59172345678",
    "cursos_inscritos": [
      { "nombre": "Node.js Avanzado", "credito": 5 },
      { "nombre": "Introducción a Python", "credito": 3 }
    ]
  },
  {
    "nombre": "Lucía Fernández",
    "email": "lucia.f@email.com",
    "telefono": "+59173456789",
    "cursos_inscritos": [
      { "nombre": "Master en MongoDB", "credito": 4 },
      { "nombre": "Introducción a Python", "credito": 3 }
    ]
  }
]
```

---

## Ventajas y Desventajas (Comparativa)

| Tipo de Modelado | Ventajas | Desventajas |
| :--- | :--- | :--- |
| **Referenciado (IDs)** | • No duplica datos (Consistencia).<br>• Documentos más pequeños.<br>• Actualizaciones fáciles en un solo lugar. | • Consultas más lentas (requiere `$lookup`/JOINs).<br>• Mayor cantidad de peticiones al servidor. |
| **Embebido (Incrustado)** | • Lecturas ultra rápidas en una sola consulta.<br>• Estructura atómica e independiente.<br>• Excelente rendimiento en apps móviles/web. | • Duplicación de datos (Riesgo de inconsistencia).<br>• Límite de tamaño por documento (BSON máx 16MB).<br>• Actualizaciones complejas. |