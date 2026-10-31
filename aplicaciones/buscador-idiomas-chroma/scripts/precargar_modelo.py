"""Descarga el modelo de embeddings una vez, antes de la clase.

La primera ejecución baja varios cientos de MB desde Hugging Face.
Conviene hacerla con buena red, no durante la demo.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MODELO = os.getenv("MODELO_EMBEDDINGS", "paraphrase-multilingual-MiniLM-L12-v2")


def main() -> None:
    print(f"Descargando y cargando «{MODELO}»…")
    from sentence_transformers import SentenceTransformer

    SentenceTransformer(MODELO)
    print("Listo. El modelo quedó en la caché local.")


if __name__ == "__main__":
    main()
