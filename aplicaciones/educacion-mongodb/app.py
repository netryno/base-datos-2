"""
Sistema académico: Alumnos, Asignaturas y Matrícula sobre MongoDB.

Monolito en un solo fichero, dividido en tres bloques:
  1. Conexión a MongoDB (la URI se toma del .env).
  2. Esquema: creación de colecciones con $jsonSchema (equivalente a
     db.createCollection del shell) e índices únicos.
  3. Aplicación web (Flask) con las operaciones sobre documentos usando
     comandos nativos de MongoDB: insert_one, find, update_one ($push, $pull)
     y aggregate ($lookup). No se usa ningún ORM/ODM.
"""
import os
import time
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError

# ============================================================================
# 1. CONEXIÓN
# ============================================================================

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "bd-educacion")

cliente = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = cliente[DB_NAME]          # equivale a:  use bd-educacion


def esperar_servidor(intentos: int = 30, espera: float = 2.0) -> None:
    """Reintenta el ping hasta que MongoDB acepte conexiones (útil en Docker)."""
    for n in range(1, intentos + 1):
        try:
            cliente.admin.command("ping")
            print(f"[db] MongoDB disponible (intento {n}).")
            return
        except ServerSelectionTimeoutError:
            print(f"[db] Esperando MongoDB... ({n}/{intentos})")
            time.sleep(espera)
    raise RuntimeError(f"No se pudo conectar a MongoDB con MONGO_URI={MONGO_URI}")


# ============================================================================
# 2. ESQUEMA DE LA BASE DE DATOS
#    Misma definición que el script del shell:  db.createCollection(...)
# ============================================================================

ESQUEMAS = {
    "alumno": {
        "bsonType": "object",
        "title": "alumno",
        "properties": {
            "_id": {"bsonType": "objectId"},
            "dni": {"bsonType": "objectId"},
            "nombre": {"bsonType": "string"},
            "edad": {"bsonType": "string"},
        },
        "additionalProperties": False,
    },
    "asignatura": {
        "bsonType": "object",
        "title": "asignatura",
        "properties": {
            "_id": {"bsonType": "objectId"},
            "gestion": {"bsonType": "string"},
            "codigo": {"bsonType": "string"},
            "nombre": {"bsonType": "string"},
            "descripcion": {"bsonType": "string"},
            "profesor": {
                "bsonType": "object",
                "properties": {
                    "dni": {"bsonType": "objectId"},
                    "nombre": {"bsonType": "string"},
                    "especialidad": {"bsonType": "string"},
                },
                "additionalProperties": False,
            },
            "inscritos": {
                "bsonType": "array",
                "additionalItems": True,
                "items": {
                    "bsonType": "object",
                    "properties": {
                        "alumno_id": {"bsonType": "objectId"},
                        "fecha_inscripcion": {"bsonType": "date"},
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    },
}


def crear_colecciones() -> None:
    """Crea las colecciones (si no existen) con su validador, y los índices."""
    existentes = db.list_collection_names()

    for nombre, esquema in ESQUEMAS.items():
        if nombre in existentes:
            print(f"[db] Colección '{nombre}' ya existe.")
            continue
        # db.createCollection("alumno", { capped, validator, validationLevel, validationAction })
        db.create_collection(
            nombre,
            capped=False,
            validator={"$jsonSchema": esquema},
            validationLevel="off",
            validationAction="warn",
        )
        print(f"[db] Colección '{nombre}' creada.")

    # Índices únicos: db.alumno.createIndex({dni: 1}, {unique: true})
    db.alumno.create_index([("dni", ASCENDING)], unique=True)
    db.asignatura.create_index([("gestion", ASCENDING), ("codigo", ASCENDING)], unique=True)
    print("[db] Índices verificados.")


# ============================================================================
# 3. APLICACIÓN WEB
# ============================================================================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave-academica")


def campo(nombre: str) -> str:
    """Lee un campo del formulario sin espacios sobrantes."""
    return request.form.get(nombre, "").strip()


def a_object_id(valor: str) -> ObjectId | None:
    """Convierte el texto de un formulario a ObjectId; None si no es válido."""
    try:
        return ObjectId(valor)
    except (InvalidId, TypeError):
        return None


# ---------------------------------------------------------------- Inicio ----

@app.get("/")
def inicio():
    resumen = {
        "base_datos": DB_NAME,
        "colecciones": sorted(db.list_collection_names()),
        "alumnos": db.alumno.count_documents({}),
        "asignaturas": db.asignatura.count_documents({}),
    }
    return render_template("inicio.html", resumen=resumen)


# --------------------------------------------------------------- Alumnos ----

@app.get("/alumnos")
def alumnos():
    # db.alumno.find().sort({nombre: 1})
    lista = list(db.alumno.find().sort("nombre", ASCENDING))
    return render_template("alumnos.html", alumnos=lista)


@app.post("/alumnos")
def registrar_alumno():
    documento = {"dni": campo("dni"), "nombre": campo("nombre"), "edad": campo("edad")}

    if not all(documento.values()):
        flash("Todos los campos del alumno son obligatorios.", "error")
        return redirect(url_for("alumnos"))

    try:
        # db.alumno.insertOne({dni, nombre, edad})
        db.alumno.insert_one(documento)
        flash(f"Alumno {documento['nombre']} registrado.", "ok")
    except DuplicateKeyError:
        flash(f"Ya existe un alumno con DNI {documento['dni']}.", "error")

    return redirect(url_for("alumnos"))


# ----------------------------------------------------------- Asignaturas ----

@app.get("/asignaturas")
def asignaturas():
    # db.asignatura.find().sort({gestion: -1, codigo: 1})
    lista = list(db.asignatura.find().sort([("gestion", -1), ("codigo", ASCENDING)]))
    return render_template("asignaturas.html", asignaturas=lista)


@app.post("/asignaturas")
def registrar_asignatura():
    documento = {
        "gestion": campo("gestion"),
        "codigo": campo("codigo").upper(),
        "nombre": campo("nombre"),
        "descripcion": campo("descripcion"),
        "profesor": {                      # documento embebido
            "dni": campo("profesor_dni"),
            "nombre": campo("profesor_nombre"),
            "especialidad": campo("profesor_especialidad"),
        },
        "inscritos": [],                   # arreglo que se llenará con $push
    }

    obligatorios = (documento["gestion"], documento["codigo"], documento["nombre"],
                    documento["profesor"]["dni"], documento["profesor"]["nombre"])
    if not all(obligatorios):
        flash("Gestión, código, nombre y los datos del profesor son obligatorios.", "error")
        return redirect(url_for("asignaturas"))

    try:
        # db.asignatura.insertOne({...})
        db.asignatura.insert_one(documento)
        flash(f"Asignatura {documento['codigo']} registrada.", "ok")
    except DuplicateKeyError:
        flash(f"Ya existe la asignatura {documento['codigo']} en la gestión {documento['gestion']}.", "error")

    return redirect(url_for("asignaturas"))


# ------------------------------------------------------------- Matrícula ----

@app.get("/matricula")
def matricula():
    asignaturas = list(db.asignatura.find({}, {"inscritos": 0}).sort([("gestion", -1), ("codigo", 1)]))
    seleccionada, inscritos, disponibles = None, [], []

    asignatura_id = a_object_id(request.args.get("asignatura_id", ""))
    if asignatura_id:
        seleccionada = db.asignatura.find_one({"_id": asignatura_id})

    if seleccionada:
        # Une cada inscrito con su alumno (equivalente a un JOIN):
        # db.asignatura.aggregate([{$match}, {$unwind}, {$lookup}, {$unwind}, {$project}, {$sort}])
        inscritos = list(db.asignatura.aggregate([
            {"$match": {"_id": asignatura_id}},
            {"$unwind": "$inscritos"},
            {"$lookup": {
                "from": "alumno",
                "localField": "inscritos.alumno_id",
                "foreignField": "_id",
                "as": "alumno",
            }},
            {"$unwind": "$alumno"},
            {"$project": {"_id": 0, "alumno": 1, "fecha_inscripcion": "$inscritos.fecha_inscripcion"}},
            {"$sort": {"alumno.nombre": 1}},
        ]))

        # Alumnos que aún no están en el arreglo inscritos
        ids_inscritos = [i["alumno_id"] for i in seleccionada.get("inscritos", [])]
        disponibles = list(db.alumno.find({"_id": {"$nin": ids_inscritos}}).sort("nombre", 1))

    return render_template(
        "matricula.html",
        asignaturas=asignaturas,
        seleccionada=seleccionada,
        inscritos=inscritos,
        disponibles=disponibles,
    )


@app.post("/matricula")
def matricular():
    asignatura_id = a_object_id(campo("asignatura_id"))
    alumno_id = a_object_id(campo("alumno_id"))

    if not asignatura_id or not alumno_id:
        flash("Debe seleccionar una asignatura y un alumno.", "error")
        return redirect(url_for("matricula"))

    # MongoDB no tiene claves foráneas: la aplicación verifica que el alumno exista.
    if not db.alumno.find_one({"_id": alumno_id}, {"_id": 1}):
        flash("El alumno seleccionado no existe.", "error")
        return redirect(url_for("matricula", asignatura_id=asignatura_id))

    # db.asignatura.updateOne(
    #   {_id, "inscritos.alumno_id": {$ne: alumno_id}},     <- evita duplicados
    #   {$push: {inscritos: {alumno_id, fecha_inscripcion: new Date()}}})
    resultado = db.asignatura.update_one(
        {"_id": asignatura_id, "inscritos.alumno_id": {"$ne": alumno_id}},
        {"$push": {"inscritos": {"alumno_id": alumno_id,
                                 "fecha_inscripcion": datetime.now(timezone.utc)}}},
    )

    if resultado.modified_count == 1:
        flash("Alumno matriculado.", "ok")
    else:
        flash("El alumno ya está inscrito en esta asignatura.", "error")

    return redirect(url_for("matricula", asignatura_id=asignatura_id))


@app.post("/matricula/retirar")
def retirar():
    asignatura_id = a_object_id(campo("asignatura_id"))
    alumno_id = a_object_id(campo("alumno_id"))

    # db.asignatura.updateOne({_id}, {$pull: {inscritos: {alumno_id}}})
    db.asignatura.update_one(
        {"_id": asignatura_id},
        {"$pull": {"inscritos": {"alumno_id": alumno_id}}},
    )
    flash("Inscripción retirada.", "ok")
    return redirect(url_for("matricula", asignatura_id=asignatura_id))


# ============================================================================
# ARRANQUE
# ============================================================================

if __name__ == "__main__":
    esperar_servidor()
    crear_colecciones()
    app.run(host="0.0.0.0", port=8000)
