"""
===========================================================================
Configuración de conexión a SQL Server
===========================================================================

Toda la configuración se lee desde variables de entorno (con valores por
defecto) para que el mismo código funcione en local y en Docker.

Variables:
- DB_HOST     → host donde corre SQL Server
- DB_PORT     → puerto (1433 por defecto)
- DB_USER     → usuario (sa en contenedores)
- DB_PASSWORD → contraseña
- DB_NAME     → nombre de la base de datos a usar/crear
"""

import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "1433")
DB_USER = os.getenv("DB_USER", "sa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "AlumnoSql2025!")
DB_NAME = os.getenv("DB_NAME", "bd_herramientas")

# Driver ODBC 18 (instalado en el Dockerfile).
DRIVER = "ODBC Driver 18 for SQL Server"


def conn_str(database: str = DB_NAME) -> str:
    """
    Construye la cadena de conexión ODBC.

    TrustServerCertificate=yes evita el error de certificado cuando el
    SQL Server usa un certificado autofirmado (caso común en contenedores).
    """
    return (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={DB_HOST},{DB_PORT};"
        f"UID={DB_USER};PWD={DB_PASSWORD};"
        f"DATABASE={database};"
        f"TrustServerCertificate=yes;Encrypt=yes"
    )
