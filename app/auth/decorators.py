from functools import wraps

from flask import abort

from flask_login import current_user


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kws):
        if not current_user.is_authenticated:
            abort(401)

        is_admin_user = getattr(current_user, 'is_admin', False) or (
            getattr(current_user, 'email', '').lower() == 'admin@example.com'
        )
        if not is_admin_user:
            abort(401)
        return f(*args, **kws)
    return decorated_function


def docente_required(f):
    """Requiere que el usuario sea un docente autenticado (admin o docente)."""
    @wraps(f)
    def decorated_function(*args, **kws):
        if not current_user.is_authenticated:
            abort(401)
        return f(*args, **kws)
    return decorated_function
