"""Configuración de la app. Todo se lee de variables de entorno (fichero .env)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _int(nombre: str, defecto: int) -> int:
    try:
        return int(os.getenv(nombre, defecto))
    except ValueError:
        return defecto


def _bool(nombre: str, defecto: bool) -> bool:
    v = os.getenv(nombre)
    return defecto if v is None else v.strip().lower() in ("1", "true", "si", "sí", "yes", "on")


APP_PORT = _int("APP_PORT", 8078)

# Partida
QUESTION_DURATION = _int("QUESTION_DURATION", 25)       # segundos por pregunta (defecto si la pregunta no define tiempo)
RESULT_REVEAL_SECONDS = _int("RESULT_REVEAL_SECONDS", 2)  # pausa acierto/error antes del ranking
TOP_N = _int("TOP_N", 10)                                # tamaño del ranking
BASE_POINTS = _int("BASE_POINTS", 10)                    # puntos por acierto
SPEED_BONUS_ENABLED = _bool("SPEED_BONUS_ENABLED", True)
SPEED_BONUS_MAX = _int("SPEED_BONUS_MAX", 5)             # bonus máximo por velocidad
ANSWER_POLICY = os.getenv("ANSWER_POLICY", "first").strip().lower()   # first | last
AUTO_ADVANCE_SECONDS = _int("AUTO_ADVANCE_SECONDS", 0)   # 0 = el profesor pulsa "Siguiente"
GAME_STATE_TTL = _int("GAME_STATE_TTL", 3600)            # segundos extra que vive el estado en Redis

# Lock del Profesor / Publicador
PUBLISHER_LOCK_TTL = _int("PUBLISHER_LOCK_TTL", 15)
HEARTBEAT_INTERVAL = _int("HEARTBEAT_INTERVAL", 5)

# SSE (/api/events): comentarios de keep-alive para que proxies/túneles no buffericen ni corten la conexión.
SSE_PING_INTERVAL = _int("SSE_PING_INTERVAL", 5)
# Si SSE no funciona (p. ej. quick tunnel de Cloudflare), sondeo GET /state cada N s; 0 = solo auto-detección en el cliente.
STATE_POLL_INTERVAL = _int("STATE_POLL_INTERVAL", 0)

# Jugadores
MIN_NAME_LENGTH = _int("MIN_NAME_LENGTH", 2)
MAX_NAME_LENGTH = _int("MAX_NAME_LENGTH", 20)


def publica() -> dict:
    """Subconjunto de la configuración que el navegador necesita conocer."""
    return {
        "question_duration": QUESTION_DURATION,
        "result_reveal_seconds": RESULT_REVEAL_SECONDS,
        "top_n": TOP_N,
        "base_points": BASE_POINTS,
        "speed_bonus_enabled": SPEED_BONUS_ENABLED,
        "speed_bonus_max": SPEED_BONUS_MAX,
        "answer_policy": ANSWER_POLICY,
        "auto_advance_seconds": AUTO_ADVANCE_SECONDS,
        "publisher_lock_ttl": PUBLISHER_LOCK_TTL,
        "heartbeat_interval": HEARTBEAT_INTERVAL,
        "sse_ping_interval": SSE_PING_INTERVAL,
        "state_poll_interval": STATE_POLL_INTERVAL,
        "min_name_length": MIN_NAME_LENGTH,
        "max_name_length": MAX_NAME_LENGTH,
    }
