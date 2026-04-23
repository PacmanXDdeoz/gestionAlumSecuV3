from pathlib import Path

from sqlalchemy.engine import make_url

from .default import *


APP_ENV = APP_ENV_DEVELOPMENT

_SECRET_DB_URI_FILE = Path(BASE_DIR) / '.db_uri.secret'

try:
	SQLALCHEMY_DATABASE_URI = make_url(_SECRET_DB_URI_FILE.read_text(encoding='utf-8').strip())
except FileNotFoundError:
	SQLALCHEMY_DATABASE_URI = make_url('sqlite:///dev.db')
