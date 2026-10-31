"""Carga los datos y muestra el top 5 por significado.

Sirve para revisar el demo antes de la clase, sin abrir el navegador.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import servicio

CONSULTAS = (
    "perro",
    "rain",
    "tristesse",
    "dinero que me pagan cada mes",
    "animal que maúlla",
    "quiero viajar por el aire",
)


def main() -> None:
    total = servicio.cargar()
    print(f"Registros en «{servicio.COLECCION}»: {total}")
    for consulta in CONSULTAS:
        print(f"\n=== {consulta} ===")
        for r in servicio.buscar_significado(consulta, n=5):
            print(f"  {r['similitud']:3d}%  {r['idioma'].upper():2}  {r['texto']}  ({r['categoria']})")


if __name__ == "__main__":
    main()
