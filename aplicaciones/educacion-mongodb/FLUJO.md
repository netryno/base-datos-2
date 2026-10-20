# Flujo de datos: de MongoDB al navegador

Resumen de cómo viaja un dato dentro de la aplicación. Se usa como ejemplo
la pantalla **Alumnos**; las demás funcionan igual.

## Piezas que intervienen

| Capa | Fichero | Tecnología | Función |
|------|---------|------------|---------|
| Base de datos | contenedor `mongo` | MongoDB | Guarda los documentos en `bd-educacion.alumno` |
| Acceso a datos | `app.py` (bloques 1 y 2) | PyMongo | Conexión y comandos nativos (`find`, `insert_one`, …) |
| Servidor web | `app.py` (bloque 3) | Flask | Recibe la petición HTTP y decide qué hacer |
| Plantilla | `templates/*.html` | Jinja2 | Convierte los documentos en HTML |
| Cliente | navegador | HTML/CSS | Muestra la página y envía formularios |

## 1. Lectura: mostrar el listado (GET)

```
Navegador                Flask (app.py)                 PyMongo / MongoDB            Jinja2
─────────                ──────────────                 ─────────────────            ──────
GET /alumnos  ────────►  @app.get("/alumnos")
                         def alumnos():
                             db.alumno.find()  ───────►  db.alumno.find().sort()
                                               ◄───────  [ {_id, dni, nombre, edad}, … ]
                             render_template(
                               "alumnos.html",
                               alumnos=lista)  ──────────────────────────────────►  {% for a in alumnos %}
                                                                                     <td>{{ a.nombre }}</td>
          ◄──────────────────────────────────────────────────────────────────────  HTML final
```

Paso a paso:

1. El navegador pide `http://localhost:8076/alumnos`.
2. Flask busca la función decorada con `@app.get("/alumnos")`.
3. La función ejecuta `db.alumno.find().sort("nombre", 1)`. PyMongo envía el
   comando al servidor MongoDB por la red Docker (`MONGO_URI` del `.env`).
4. MongoDB devuelve un cursor; `list(...)` lo convierte en una lista de
   diccionarios Python (cada uno es un documento BSON tal cual está guardado).
5. `render_template("alumnos.html", alumnos=lista)` entrega esa lista a Jinja2.
6. Jinja2 recorre `{% for a in alumnos %}` e inserta `{{ a.dni }}`,
   `{{ a.nombre }}` dentro del HTML de la plantilla (que a su vez extiende
   `base.html`, de donde sale el menú).
7. Flask responde con el HTML terminado; el navegador lo pinta usando
   `static/estilo.css`.

## 2. Escritura: registrar un alumno (POST)

```
Navegador                       Flask (app.py)                     MongoDB
─────────                       ──────────────                     ───────
<form method="post">
POST /alumnos
dni=…&nombre=…&edad=…  ──────►  @app.post("/alumnos")
                                def registrar_alumno():
                                    request.form[...]
                                    db.alumno.insert_one(doc) ───►  insertOne  (índice único en dni)
                                                              ◄───  ok | DuplicateKeyError
                                    flash("Alumno registrado")
                                    redirect("/alumnos")
          ◄──────────────────── 302 Location: /alumnos
GET /alumnos  ─────────────────► (vuelve al flujo de lectura del punto 1;
                                  base.html muestra el mensaje con get_flashed_messages)
```

Puntos clave:

- Los campos del formulario llegan en `request.form`; la función arma un
  diccionario y lo inserta **sin transformación ni ORM**: el diccionario Python
  es el documento MongoDB.
- Si el índice único rechaza el DNI, PyMongo lanza `DuplicateKeyError` y la
  función lo convierte en un aviso para el usuario.
- Tras un POST siempre se redirige a un GET (patrón *Post/Redirect/Get*), así
  recargar la página no repite la inserción.

## 3. Caso con relación: inscritos de una asignatura

`inscritos` guarda solo el `alumno_id`. Para mostrar nombre y DNI se usa una
agregación que hace el papel del JOIN:

```
db.asignatura.aggregate([
  {$match:  {_id: asignatura_id}},          # la asignatura elegida
  {$unwind: "$inscritos"},                  # un documento por inscrito
  {$lookup: {from: "alumno",                # trae el alumno por su _id
             localField: "inscritos.alumno_id",
             foreignField: "_id", as: "alumno"}},
  {$unwind: "$alumno"},
  {$project: {alumno: 1, fecha_inscripcion: "$inscritos.fecha_inscripcion"}}
])
```

El resultado (`[{alumno: {...}, fecha_inscripcion}, …]`) pasa a
`matricula.html`, que lo recorre igual que en el punto 1.

## 4. Arranque del contenedor

```
docker compose up
  └─ python app.py
       ├─ load_dotenv()            lee MONGO_URI y DB_NAME del .env
       ├─ esperar_servidor()       ping hasta que MongoDB responda
       ├─ crear_colecciones()      createCollection + $jsonSchema + índices (solo si no existen)
       └─ app.run(port=8000)       Flask queda escuchando; Docker lo publica en APP_PORT (8076)
```
