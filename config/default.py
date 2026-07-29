from pathlib import Path

from sqlalchemy.engine import make_url
from os.path import abspath, dirname


# Define the application directory
BASE_DIR = dirname(dirname(abspath(__file__)))

SECRET_KEY = '7110c8ae51a4b5af97be6534caef90e4bb9bdcb3380af008f90b23a5d1616bf319bc298105da20fe'

# Database configuration
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Database URI leída desde archivo secreto (PostgreSQL)
_SECRET_DB_URI_FILE = Path(BASE_DIR) / 'db_uri.secret'
try:
    SQLALCHEMY_DATABASE_URI = make_url(
        _SECRET_DB_URI_FILE.read_text(encoding='utf-8').strip()
    )
except FileNotFoundError:
    raise RuntimeError(
        'No se encontró el archivo db_uri.secret con la URI de PostgreSQL. '
        'Copia la URI de conexión en ese archivo para continuar.'
    )

# App environments
APP_ENV_LOCAL = 'local'
APP_ENV_TESTING = 'testing'
APP_ENV_DEVELOPMENT = 'development'
APP_ENV_STAGING = 'staging'
APP_ENV_PRODUCTION = 'production'
APP_ENV = ''

# Configuración del email
MAIL_SERVER = 'tu servidor smtp'
MAIL_PORT = 587
MAIL_USERNAME = 'tu correo'
MAIL_PASSWORD = 'tu contraseña'
DONT_REPLY_FROM_EMAIL = 'dirección from'
ADMINS = ('user@prueba.com', )
MAIL_USE_TLS = True
MAIL_DEBUG = False

ITEMS_PER_PAGE = 3
