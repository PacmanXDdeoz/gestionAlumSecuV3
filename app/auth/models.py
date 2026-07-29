from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

from app import db


class User(db.Model, UserMixin):

    __tablename__ = 'blog_user'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(256), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def __init__(self, name, email):
        self.name = name
        self.email = email

    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def get_by_id(id):
        return User.query.get(id)

    @staticmethod
    def get_by_email(email):
        return User.query.filter_by(email=email).first()

    @staticmethod
    def get_all():
        return User.query.all()

class Docente(db.Model, UserMixin):
    __tablename__ = 'docentes'
    __table_args__ = {'schema': 'alejandra'}

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default='docente')
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

    def __init__(self, name, email, apellidos="", rol='docente', estatus=True):
        self.nombre = name
        self.apellidos = apellidos
        self.email = email
        self.rol = rol
        self.estatus = estatus

    @property
    def is_admin(self):
        return self.rol == 'admin'

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