from .default import *


APP_ENV = APP_ENV_PRODUCTION

# Producción no define SECRET_KEY ni SQLALCHEMY_DATABASE_URI: ambos se leen
# desde .env (SECRET_KEY y DATABASE_URI). Nunca hardcodear credenciales.
