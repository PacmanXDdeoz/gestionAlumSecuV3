from flask import Blueprint

auth_bp = Blueprint('auth', __name__, template_folder='templates')

# Importa las rutas solo cuando el blueprint sea registrado por la app.
# Esto evita ciclos de importación al cargar modelos desde app.models.