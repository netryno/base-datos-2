"""Cliente de Chroma y las dos búsquedas del demo.

La exacta recorre los textos en memoria (como ILIKE).
La de significado pregunta a la colección vectorial.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")

import chromadb
from chromadb.config import Settings
from chromadb.errors import NotFoundError
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from dotenv import load_dotenv

from datos import IDIOMAS, construir_registros

load_dotenv(Path(__file__).resolve().parent / ".env")

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_TENANT = os.getenv("CHROMA_TENANT", "default_tenant")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE", "default_database")
COLECCION = os.getenv("COLECCION", "multilingue")
MODELO = os.getenv("MODELO_EMBEDDINGS", "paraphrase-multilingual-MiniLM-L12-v2")

_lock = threading.RLock()
_cliente = None
_ef = None


class ErrorChroma(Exception):
    """No se pudo usar Chroma. El mensaje ya está en español."""


def mensaje_conexion() -> str:
    return f"No se pudo conectar con Chroma en {CHROMA_HOST}:{CHROMA_PORT}"


def funcion_embeddings():
    """El modelo se carga una sola vez: la primera llamada puede tardar."""
    global _ef
    if _ef is None:
        with _lock:
            if _ef is None:
                _ef = SentenceTransformerEmbeddingFunction(model_name=MODELO)
    return _ef


def obtener_cliente():
    global _cliente
    if _cliente is None:
        _cliente = chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            tenant=CHROMA_TENANT,
            database=CHROMA_DATABASE,
            settings=Settings(anonymized_telemetry=False),
        )
    return _cliente


def busqueda_exacta(consulta: str) -> list[dict]:
    """WHERE texto ILIKE '%consulta%'. No usa Chroma."""
    q = consulta.strip().casefold()
    if not q:
        return []
    _, documentos, metadatos = construir_registros()
    return [
        {"texto": texto, "idioma": meta["idioma"], "categoria": meta["categoria"]}
        for texto, meta in zip(documentos, metadatos)
        if q in texto.casefold()
    ]


def buscar(consulta: str, n: int = 8, idiomas: list[str] | None = None) -> dict:
    return {
        "exacta": busqueda_exacta(consulta),
        "significado": buscar_significado(consulta, n=n, idiomas=idiomas),
    }


def buscar_significado(consulta: str, n: int = 8, idiomas: list[str] | None = None) -> list[dict]:
    with _lock:
        return _buscar_significado(consulta, n, idiomas)


def cargar() -> int:
    """Upsert de los 148 registros. Se puede ejecutar varias veces: no duplica."""
    with _lock:
        return _cargar()


def reiniciar() -> int:
    """Borra la colección y la vuelve a cargar."""
    with _lock:
        _borrar_coleccion()
        return _cargar()


def estado() -> dict:
    info = {
        "conectado": False,
        "modelo": MODELO,
        "coleccion": COLECCION,
        "registros": 0,
        "host": CHROMA_HOST,
        "port": CHROMA_PORT,
    }
    try:
        cliente = obtener_cliente()
        cliente.heartbeat()
    except Exception as e:
        info["error"] = str(_traducir(e))
        return info

    info["conectado"] = True
    try:
        if COLECCION in {c.name for c in cliente.list_collections()}:
            col = cliente.get_collection(name=COLECCION, embedding_function=funcion_embeddings())
            info["registros"] = col.count()
    except Exception as e:
        info["error"] = str(_traducir(e))
    return info


# ----------------------------------------------------------------- interno ----

def _cargar() -> int:
    ids, documentos, metadatos = construir_registros()
    col = _obtener_coleccion()
    # Sin embeddings en la llamada: los calcula la función de la colección.
    col.upsert(ids=ids, documents=documentos, metadatas=metadatos)
    _verificar_coseno(col, documentos[0])
    return col.count()


def _borrar_coleccion() -> None:
    try:
        obtener_cliente().delete_collection(name=COLECCION)
    except NotFoundError:
        return
    except Exception as e:
        if "not found" in str(e).lower() or "does not exist" in str(e).lower():
            return
        raise _traducir(e) from e


def _obtener_coleccion():
    ef = funcion_embeddings()
    try:
        cliente = obtener_cliente()
        try:
            col = cliente.get_or_create_collection(
                name=COLECCION,
                embedding_function=ef,
                configuration={"hnsw": {"space": "cosine"}},
            )
        except TypeError:
            col = _coleccion_con_metadata(cliente, ef)
        except Exception as e:
            if _es_conexion(e) or not _rechaza_configuracion(e):
                raise
            col = _coleccion_con_metadata(cliente, ef)
    except ErrorChroma:
        raise
    except Exception as e:
        raise _traducir(e) from e

    espacio = _espacio(col)
    if espacio and espacio != "cosine":
        raise ErrorChroma(
            f"La colección «{COLECCION}» usa distancia {espacio}, no coseno. "
            "Pulsa Reiniciar demo para crearla de nuevo."
        )
    return col


def _coleccion_con_metadata(cliente, ef):
    return cliente.get_or_create_collection(
        name=COLECCION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def _verificar_coseno(col, texto: str) -> None:
    """Un texto idéntico a uno guardado debe quedar a distancia ≈ 0."""
    resultado = col.query(query_texts=[texto], n_results=1, include=["distances"])
    distancias = (resultado.get("distances") or [[]])[0]
    if not distancias or distancias[0] > 0.05:
        distancia = distancias[0] if distancias else None
        raise ErrorChroma(
            "Un texto idéntico no quedó a distancia ≈ 0 "
            f"(llegó {distancia}). Revisa que la colección use coseno."
        )


def _buscar_significado(consulta: str, n: int, idiomas: list[str] | None) -> list[dict]:
    consulta = consulta.strip()
    if not consulta:
        return []
    where = _filtro_idioma(idiomas)
    if where is False:
        return []
    try:
        col = _obtener_coleccion()
        disponibles = _cuantos(col, where)
        if disponibles == 0:
            return []
        n = max(1, min(n, disponibles))
        kwargs = {
            "query_texts": [consulta],
            "n_results": n,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        resultado = col.query(**kwargs)
    except ErrorChroma:
        raise
    except Exception as e:
        raise _traducir(e) from e
    return _formatear(resultado)


def _filtro_idioma(idiomas: list[str] | None):
    """None: todos los idiomas. False: el filtro dejó la lista vacía."""
    if idiomas is None:
        return None
    elegidos = [i for i in idiomas if i in IDIOMAS]
    if not elegidos:
        return False
    if set(elegidos) == set(IDIOMAS):
        return None
    return {"idioma": {"$in": elegidos}}


def _cuantos(col, where) -> int:
    if not where:
        return col.count()
    encontrados = col.get(where=where, include=["metadatas"])
    return len(encontrados["ids"])


def _formatear(resultado) -> list[dict]:
    documentos = (resultado.get("documents") or [[]])[0] or []
    metadatos = (resultado.get("metadatas") or [[]])[0] or []
    distancias = (resultado.get("distances") or [[]])[0] or []
    salida = []
    for texto, meta, distancia in zip(documentos, metadatos, distancias):
        meta = meta or {}
        similitud = max(0, min(100, round((1 - distancia) * 100)))
        salida.append({
            "texto": texto,
            "idioma": meta.get("idioma", ""),
            "categoria": meta.get("categoria", ""),
            "similitud": similitud,
        })
    return salida


def _espacio(col) -> str | None:
    meta = col.metadata or {}
    if meta.get("hnsw:space"):
        return meta["hnsw:space"]
    config = getattr(col, "configuration", None)
    if config is None:
        config = getattr(getattr(col, "_model", None), "configuration_json", None)
    if isinstance(config, dict):
        hnsw = config.get("hnsw") or {}
        if isinstance(hnsw, dict):
            return hnsw.get("space")
    hnsw = getattr(config, "hnsw", None)
    return getattr(hnsw, "space", None) if hnsw is not None else None


def _rechaza_configuracion(error: Exception) -> bool:
    texto = str(error).lower()
    return any(p in texto for p in ("configuration", "unexpected keyword", "hnsw", "extra"))


def _es_conexion(error: Exception) -> bool:
    nombre = type(error).__name__.lower()
    texto = str(error).lower()
    if "connect" in nombre or "timeout" in nombre:
        return True
    return any(p in texto for p in (
        "could not connect",
        "connection refused",
        "connection error",
        "failed to establish a new connection",
        "name or service not known",
        "nodename nor servname",
        "network is unreachable",
        "timed out",
    ))


def _traducir(error: Exception) -> ErrorChroma:
    if isinstance(error, ErrorChroma):
        return error
    if _es_conexion(error):
        return ErrorChroma(mensaje_conexion())
    texto = str(error).lower()
    if "embedding function" in texto:
        return ErrorChroma(
            "La colección ya existe con otro modelo de embeddings. "
            "Pulsa Reiniciar demo para crearla de nuevo."
        )
    return ErrorChroma(f"Error de Chroma: {error}")
