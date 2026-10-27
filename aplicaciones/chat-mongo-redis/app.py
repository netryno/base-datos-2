"""Servidor web (Flask): sirve la interfaz y expone la API JSON de los tres widgets."""
from flask import Flask, Response, jsonify, render_template, request

import cache
import pubsub

app = Flask(__name__)


@app.get("/")
def inicio():
    return render_template("index.html")


# ------------------------------------------------- Widget 1 · Caché ----

@app.get("/api/asignaturas")
def asignaturas():
    return jsonify(cache.codigos_asignaturas())


@app.get("/api/cache/<codigo>")
def consultar(codigo):
    return jsonify(cache.obtener_asignatura(codigo))


@app.delete("/api/cache/<codigo>")
def vaciar(codigo):
    return jsonify(cache.vaciar_asignatura(codigo))


# ------------------------------------------- Widgets 2 y 3 · Pub/Sub ----

def token() -> str:
    return (request.get_json(silent=True) or {}).get("token", "")


@app.get("/api/publicador")
def estado_publicador():
    return jsonify(pubsub.estado_lock())


@app.post("/api/publicador/entrar")
def entrar_publicador():
    if pubsub.adquirir_lock(token()):
        return jsonify({"ok": True, "ttl": pubsub.LOCK_TTL})
    return jsonify({"ok": False, "error": "Ya hay un publicador activo."}), 409


@app.post("/api/publicador/renovar")
def renovar_publicador():
    return jsonify({"ttl": pubsub.renovar_lock(token())})


@app.post("/api/publicador/salir")
def salir_publicador():
    pubsub.liberar_lock(token())
    return jsonify({"ok": True})


@app.post("/api/publicar")
def publicar():
    datos = request.get_json(silent=True) or {}
    resultado = pubsub.publicar(datos.get("token", ""), datos.get("canal", ""), datos.get("mensaje", {}))
    return jsonify(resultado), 403 if "error" in resultado else 200


@app.get("/api/suscribir")
def suscribir():
    return Response(pubsub.escuchar(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8077, threaded=True)
