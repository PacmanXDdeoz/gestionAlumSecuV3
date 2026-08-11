"""Configuración base de la aplicación.

Todos los valores sensibles se leen desde variables de entorno o desde el
archivo ``.env`` (ver ``.env.example``). No debe haber secretos hardcodeados.
"""
import os
from pathlib import Path

from sqlalchemy.engine import make_url

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent


# ── Carga de .env ──────────────────────────────────────────────────────────
def _load_env_file(path: Path) -> None:
    """Carga un archivo .env sin depender de python-dotenv (fallback mínimo)."""
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback sin la dependencia instalada
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(BASE_DIR / '.env')
else:
    _load_env_file(BASE_DIR / '.env')


# ── Secretos y credenciales (siempre desde el entorno) ─────────────────────
def _get_secret_key() -> str:
    key = os.environ.get('SECRET_KEY', '').strip()
    if key:
        return key
    raise RuntimeError(
        'SECRET_KEY no está definida. Crea un archivo .env a partir de '
        '.env.example con una clave aleatoria.'
    )


SECRET_KEY = _get_secret_key()


# ── Base de datos ──────────────────────────────────────────────────────────
def _get_database_uri():
    uri = os.environ.get('DATABASE_URI', '').strip()
    if uri:
        return make_url(uri)
    # Compatibilidad: archivo db_uri.secret ya existente en el proyecto
    secret_file = BASE_DIR / 'db_uri.secret'
    if secret_file.exists():
        return make_url(secret_file.read_text(encoding='utf-8').strip())
    raise RuntimeError(
        'Define DATABASE_URI en el archivo .env o crea db_uri.secret con la '
        'URI de conexión de PostgreSQL.'
    )


SQLALCHEMY_DATABASE_URI = _get_database_uri()
SQLALCHEMY_TRACK_MODIFICATIONS = False

# URI de la base LOCAL de respaldo / desarrollo secundario (opcional).
# Se define en .env con DATABASE_URI_LOCAL. La app principal sigue usando
# SQLALCHEMY_DATABASE_URI (AlwaysData); esta se expone para herramientas de
# backup/restore y entornos secundarios.
DATABASE_URI_LOCAL = os.environ.get('DATABASE_URI_LOCAL', '').strip()

# URL pública base de la aplicación (ej. https://gestalumn.alwaysdata.net).
# Se usa para construir la URL absoluta que codifican los QRs cuando no hay
# contexto de request (comando ``flask regenerate-qrs``). En web, url_for
# usa el host de la petición; esta es solo el respaldo determinista.
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '').strip()
# Guard anti-placeholder: si llega literalmente un valor con '<' (p. ej. el
# template 'https://<tu-app>.onrender.com' copiado a Render sin editar), se
# trata como NO configurada: en web el QR usa el host real de la petición y
# nunca codifica un placeholder. Fuera de request, ``regenerate-qrs`` avisa
# que falta la variable en lugar de generar URLs rotas.
if '<' in PUBLIC_BASE_URL:
    PUBLIC_BASE_URL = ''

# Carpeta donde se guardan los QRs de los alumnos. Por defecto
# ``<static>/qrcodes`` (carpeta del proyecto). Se puede redirigir a otra
# ruta absoluta, p. ej. en el entorno de testing se apunta a un directorio
# temporal para que la suite de tests NUNCA escriba archivos de alumnos de
# prueba (IDs bajos) sobre la carpeta real de QRs: esos archivos parecerían
# corresponder a alumnos ya eliminados de la BD.
QR_CODES_FOLDER = os.environ.get('QR_CODES_FOLDER', '').strip() or None

# Emails con privilegios de administrador (además del rol admin = id 1 del
# catálogo alejandra.rol). Se configuran en .env, nunca hardcodeados en el código.
ADMIN_EMAILS = [
    e.strip().lower()
    for e in os.environ.get('ADMIN_EMAILS', '').split(',')
    if e.strip()
]

# ── Entornos de la aplicación ──────────────────────────────────────────────
APP_ENV_LOCAL = 'local'
APP_ENV_TESTING = 'testing'
APP_ENV_DEVELOPMENT = 'development'
APP_ENV_STAGING = 'staging'
APP_ENV_PRODUCTION = 'production'
APP_ENV = ''

# ── Configuración del email (alertas de error en producción) ───────────────
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
DONT_REPLY_FROM_EMAIL = os.environ.get('MAIL_FROM', 'no-reply@escuela.local')
ADMINS = tuple(
    a.strip()
    for a in os.environ.get('MAIL_ADMINS', 'admin@escuela.local').split(',')
    if a.strip()
)

ITEMS_PER_PAGE = 3
