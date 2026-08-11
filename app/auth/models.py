import datetime
import logging

from flask import current_app
from flask_login import UserMixin
from sqlalchemy.exc import ProgrammingError
from werkzeug.security import generate_password_hash, check_password_hash

from app import db

logger = logging.getLogger(__name__)

# IDs de rol en el catálogo alejandra.rol (fuente única, coinciden con el seed).
ROL_ADMIN_ID = 1
ROL_DOCENTE_ID = 2


class Rol(db.Model):
    """Catálogo de roles que autorizan el acceso al sistema.

    La tabla ``alejandra.rol`` es la fuente de verdad de los roles válidos
    (``admin`` / ``docente``). El login valida el rol del docente contra este
    catálogo y el formulario de docentes solo permite asignar roles presentes
    en él.

    La tabla se crea y siembra de forma idempotente con ``seed_defaults()``
    (invocado desde ``ensure_required_tables()``), por lo que una base nueva
    queda lista sin migraciones adicionales. Si el catálogo no existe o está
    vacío, las validaciones se degradan con gracia (con un warning en el log)
    en lugar de bloquear todos los accesos.
    """

    __tablename__ = 'rol'
    __table_args__ = {'schema': 'alejandra'}

    id = db.Column(db.Integer, primary_key=True)
    rol = db.Column(db.String(50), nullable=False, unique=True)

    def __repr__(self):
        return f'<Rol {self.rol}>'

    @staticmethod
    def seed_defaults():
        """Siembra los roles por defecto (admin, docente) si el catálogo está vacío."""
        try:
            if Rol.query.count() == 0:
                db.session.add_all([
                    Rol(id=1, rol='admin'),
                    Rol(id=2, rol='docente'),
                ])
                db.session.commit()
        except ProgrammingError:  # pragma: no cover - tabla aún no creada
            logger.warning('alejandra.rol no existe; se omitió el seed de roles.')

    @staticmethod
    def get_all():
        """Retorna los roles del catálogo ordenados por id."""
        try:
            return Rol.query.order_by(Rol.id.asc()).all()
        except ProgrammingError:  # pragma: no cover - tabla ausente (BD nueva)
            logger.warning('alejandra.rol no existe; catálogo de roles vacío.')
            return []

    @staticmethod
    def es_valido(rol_id) -> bool:
        """¿Existe el id de rol en el catálogo?

        Si la tabla no existe o el catálogo está vacío (base sin sembrar), se
        devuelve ``True`` para no bloquear accesos de forma silenciosa.
        """
        try:
            total = Rol.query.count()
            if total == 0:  # catálogo ausente o sin sembrar: no hay contra qué validar
                return True
            return db.session.get(Rol, rol_id) is not None
        except ProgrammingError:  # pragma: no cover - tabla ausente (BD nueva)
            return True

def es_admin(user) -> bool:
    """¿El usuario tiene privilegios de administrador?

    Se considera admin si su rol es el id ``1`` del catálogo ``alejandra.rol``
    (admin) o si su email figura en la configuración ``ADMIN_EMAILS``
    (definida en .env). Los emails privilegiados se configuran, nunca se
    hardcodean en el código.
    """
    if user is None:
        return False
    if getattr(user, 'rol', None) == ROL_ADMIN_ID:
        return True
    email = (getattr(user, 'email', '') or '').strip().lower()
    if not email:
        return False
    admins = current_app.config.get('ADMIN_EMAILS', [])
    return email in {a.strip().lower() for a in admins}


class Docente(db.Model, UserMixin):
    __tablename__ = 'docentes'
    __table_args__ = {'schema': 'alejandra'}

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    # Referencia al catálogo alejandra.rol: 1=admin, 2=docente
    rol = db.Column(db.Integer, db.ForeignKey('alejandra.rol.id'), nullable=False, default=ROL_DOCENTE_ID)
    estatus = db.Column(db.Boolean, default=True)
    creado_en = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # ── Relaciones con materias y horarios ──────────────────────────
    # Nota: la tabla 'materias_docentes' se importa con lazy loading
    # para evitar circular imports. Se resuelve en el primer acceso.
    materias = db.relationship(
        'Materia',
        secondary='alejandra.materias_docentes',
        back_populates='docentes',
        lazy='dynamic'
    )
    horarios = db.relationship(
        'Horario',
        backref='docente',
        lazy=True,
        foreign_keys='Horario.docente_id'
    )

    def __init__(self, name, email, apellidos="", rol=ROL_DOCENTE_ID, estatus=True):
        self.nombre = name
        self.apellidos = apellidos
        self.email = email
        self.rol = rol
        self.estatus = estatus

    @property
    def is_admin(self):
        return es_admin(self)

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def get_by_id(id):
        return db.session.get(Docente, id)

    @staticmethod
    def get_by_email(email):
        return Docente.query.filter_by(email=email).first()

    @staticmethod
    def get_all():
        return Docente.query.all()