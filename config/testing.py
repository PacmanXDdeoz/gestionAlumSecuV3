import tempfile

from .default import *


# Parámetros para activar el modo debug
TESTING = True
DEBUG = True

APP_ENV = APP_ENV_TESTING

WTF_CSRF_ENABLED = False

# Emails tratados como administradores en el entorno de pruebas
ADMIN_EMAILS = ['admin@example.com']

# Los QRs de los alumnos de prueba se escriben en un directorio temporal
# fuera del proyecto, NUNCA en la carpeta real app/static/qrcodes/: los
# alumnos de testing usan IDs bajos (1, 2, …) que coinciden con los de
# alumnos reales ya eliminados de la BD y sus PNGs parecerían QRs de
# alumnos que ya no existen.
QR_CODES_FOLDER = tempfile.mkdtemp(prefix='gestalumn_test_qrcodes_')
