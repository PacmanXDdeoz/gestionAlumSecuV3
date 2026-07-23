import datetime

from slugify import slugify
from sqlalchemy.exc import IntegrityError

from app import db
from app.auth.models import Docente

class Grupos(db.Model):
    __tablename__='grupos'
    __table_args__ = {'schema': 'alejandra'}
    id = db.Column(db.Integer, primary_key=True)
    grado = db.Column(db.String(1), nullable=False)
    grupo = db.Column(db.String(1), nullable=False)

    alumnos = db.relationship('Alumno', backref='grupo_info', lazy=True)

    def __init__(self, grado, grupo):
        self.grado = grado
        self.grupo = grupo

    def __repr__(self):
        return f'<Grupo {self.grado} {self.grupo}'

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()


class Alumno(db.Model):
    __tablename__='alumnos'
    __table_args__ = {'schema': 'alejandra'}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    lastname_p = db.Column(db.String(50), nullable=False)
    lastname_m = db.Column(db.String(50), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('alejandra.grupos.id'), nullable=False)
    genero = db.Column(db.String(10), nullable=False)
    status = db.Column(db.Boolean, nullable=False, default=True)
    codigo_qr = db.Column(db.String(255), unique=True, nullable=True)
    codigo_barras = db.Column(db.String(255), unique=True, nullable=True)

    password = db.Column('pass', db.String(10), nullable=False)

    calificaciones = db.relationship('Calificacion', backref='alumno', lazy=True)

    def __init__(self, name, lastname_p, lastname_m, group_id, genero, password, status=True):
        self.name = name
        self.lastname_p = lastname_p
        self.lastname_m = lastname_m
        self.group_id = group_id
        self.genero = genero
        self.status = status
        self.password = password

    def __repr__(self):
        return f'<Alumno {self.name} {self.lastname_p}>'

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

class Calificacion(db.Model):
    __tablename__ = 'calificaciones'
    __table_args__ = {'schema': 'alejandra'}
    
    id = db.Column(db.Integer, primary_key=True)
    alumnos_id = db.Column(db.Integer, db.ForeignKey('alejandra.alumnos.id'), nullable=False) 
    español = db.Column(db.Numeric)
    matematicas = db.Column(db.Numeric)
    ciencias = db.Column(db.Numeric)
    geografia = db.Column(db.Numeric)
    historia = db.Column(db.Numeric)
    f_civica = db.Column(db.Numeric)
    ingles = db.Column(db.Numeric)
    artes = db.Column(db.Numeric)
    f_español = db.Column(db.Numeric)
    f_matematicas = db.Column(db.Numeric)
    tecnologia = db.Column(db.Numeric)
    def __init__(self, alumnos_id, español=None, matematicas=None, ciencias=None, 
                 geografia=None, historia=None, f_civica=None, ingles=None, 
                 artes=None, f_español=None, f_matematicas=None, tecnologia=None):
        self.alumnos_id = alumnos_id
        self.español = español
        self.matematicas = matematicas
        self.ciencias = ciencias
        self.geografia = geografia
        self.historia = historia
        self.f_civica = f_civica
        self.ingles = ingles
        self.artes = artes
        self.f_español = f_español
        self.f_matematicas = f_matematicas
        self.tecnologia = tecnologia
    def __repr__(self):
        return f'<Calificaciones del Alumno_ID: {self.alumnos_id}>'
        
    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()
    def delete(self):
        db.session.delete(self)
        db.session.commit()

class HistorialLog(db.Model):
    __tablename__ = 'historial_logs'
    __table_args__ = {'schema': 'alejandra'}

    id = db.Column(db.Integer, primary_key=True)
    docente_id = db.Column(
        db.Integer,
        db.ForeignKey('alejandra.docentes.id'),
        nullable=True
    )
    accion = db.Column(db.String(20), nullable=False)
    tabla_afectada = db.Column(db.String(50), nullable=False)
    registro_afectado_id = db.Column(db.Integer, nullable=False)
    detalles = db.Column(db.Text, nullable=True)
    fecha_accion = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    docente = db.relationship('Docente', backref='historial_logs')