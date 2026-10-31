"""Servidor web (Flask): sirve la página del buscador y la API JSON."""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

import servicio
from servicio import ErrorChroma

app = Flask(__name__)


@app.get("/")
def inicio():
    return render_template("index.html")


@app.get("/api/estado")
def estado():
    return jsonify(servicio.estado())


@app.post("/api/cargar")
def cargar():
    try:
        return jsonify({"ok": True, "registros": servicio.cargar()})
    except ErrorChroma as e:
        app.logger.warning("%s", e)
        return jsonify({"ok": False, "error": str(e)}), 503


@app.post("/api/reiniciar")
def reiniciar():
    try:
        return jsonify({"ok": True, "registros": servicio.reiniciar()})
    except ErrorChroma as e:
        app.logger.warning("%s", e)
        return jsonify({"ok": False, "error": str(e)}), 503


@app.get("/api/buscar")
def buscar():
    q = request.args.get("q", "")
    try:
        n = int(request.args.get("n", "8"))
    except ValueError:
        n = 8
    n = min(max(n, 1), 20)

    if "idiomas" in request.args:
        idiomas = [p.strip().lower() for p in request.args.get("idiomas", "").split(",") if p.strip()]
    else:
        idiomas = None

    try:
        return jsonify(servicio.buscar(q, n=n, idiomas=idiomas))
    except ErrorChroma as e:
        # La búsqueda exacta no usa Chroma: se sigue mostrando.
        app.logger.warning("%s", e)
        return jsonify({
            "exacta": servicio.busqueda_exacta(q),
            "significado": [],
            "error": str(e),
        })


if __name__ == "__main__":
    print(f"Cargando el modelo {servicio.MODELO}…")
    print("La primera vez lo descarga desde Hugging Face y puede tardar.")
    servicio.funcion_embeddings()
    puerto = int(os.getenv("APP_PORT", "8120"))
    print(f"Buscador listo en http://localhost:{puerto}")
    app.run(host="0.0.0.0", port=puerto, threaded=True)
