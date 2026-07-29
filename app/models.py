import datetime

from slugify import slugify
from sqlalchemy.exc import IntegrityError

from app import db
from app.auth.models import Docente


# ──────────────────────────────────────────────
#  TABLA DE ASOCIACIÓN: Docente ↔ Materia
# ──────────────────────────────────────────────
materias_docentes = db.Table(
    'materias_docentes',
    db.Model.metadata,
    db.Column('docente_id', db.Integer, db.ForeignKey('alejandra.docentes.id'), primary_key=True),
    db.Column('materia_id', db.Integer, db.ForeignKey('alejandra.materias.id'), primary_key=True),
    schema='alejandra'
)


class Materia(db.Model):
    """Materia / asignatura escolar."""
    __tablename__ = 'materias'
    __table_args__ = {'schema': 'alejandra'}

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    descripcion = db.Column(db.Text, nullable=True)

    # Relaciones
    docentes = db.relationship('Docente', secondary=materias_docentes, back_populates='materias', lazy='dynamic')
    horarios = db.relationship('Horario', backref='materia', lazy=True)
    calificaciones_materia = db.relationship('CalificacionMateria', backref='materia', lazy=True)

    def __init__(self, nombre, descripcion=None):
        self.nombre = nombre
        self.descripcion = descripcion

    def __repr__(self):
        return f'<Materia {self.nombre}>'

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
        }

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def seed_materias():
        """Crea las materias por defecto si no existen."""
        materias_default = [
            ('Español', 'Lengua y literatura'),
            ('Matemáticas', 'Matemáticas'),
            ('Ciencias', 'Ciencias Naturales'),
            ('Geografía', 'Geografía'),
            ('Historia', 'Historia'),
            ('Formación Cívica y Ética', 'Formación Cívica y Ética'),
            ('Inglés', 'Inglés'),
            ('Artes', 'Artes'),
            ('Fortalecimiento de Español', 'Fortalecimiento de Español'),
            ('Fortalecimiento de Matemáticas', 'Fortalecimiento de Matemáticas'),
            ('Tecnología', 'Tecnología'),
        ]
        for nombre, desc in materias_default:
            if not Materia.query.filter_by(nombre=nombre).first():
                db.session.add(Materia(nombre=nombre, descripcion=desc))
        db.session.commit()


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

    @property
    def full_name(self):
        return ' '.join(part for part in [self.name, self.lastname_p, self.lastname_m] if part)

    @staticmethod
    def find_by_code(code):
        return Alumno.query.filter_by(password=code).first()

    def generate_qr_code(self, texto=None):
        from pathlib import Path
        import qrcode
        from flask import current_app

        if texto is None:
            texto = str(self.id)

        qr_folder = Path(current_app.static_folder) / 'qrcodes'
        qr_folder.mkdir(parents=True, exist_ok=True)
        qr_filename = f'alumno_{self.id}.png'
        qr_path = qr_folder / qr_filename
        qr_image = qrcode.make(texto)
        qr_image.save(qr_path)

        self.codigo_qr = f'qrcodes/{qr_filename}'
        if not self.id:
            db.session.add(self)
        db.session.commit()
        return self.codigo_qr

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.name,
            'apellido_paterno': self.lastname_p,
            'apellido_materno': self.lastname_m,
            'full_name': self.full_name,
            'grupo_id': self.group_id,
            'genero': self.genero,
            'estatus': self.status,
            'codigo_qr': self.codigo_qr,
            'codigo_barras': self.codigo_barras,
        }

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


class Horario(db.Model):
    """Horario de clases de un docente.

    Cada entrada representa un bloque de clase: un día, una hora,
    una materia y un salón asignado a un docente específico.
    """
    __tablename__ = 'horarios'
    __table_args__ = {'schema': 'alejandra'}

    id = db.Column(db.Integer, primary_key=True)
    docente_id = db.Column(
        db.Integer,
        db.ForeignKey('alejandra.docentes.id'),
        nullable=False
    )
    materia_id = db.Column(
        db.Integer,
        db.ForeignKey('alejandra.materias.id'),
        nullable=False
    )
    dia_semana = db.Column(db.Integer, nullable=False)  # 1=Lunes … 7=Domingo
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    salon = db.Column(db.String(20), nullable=True)

    # Relación backref: docente desde Docente, materia desde Materia
    def __init__(self, docente_id, materia_id, dia_semana, hora_inicio, hora_fin, salon=None):
        self.docente_id = docente_id
        self.materia_id = materia_id
        self.dia_semana = dia_semana
        self.hora_inicio = hora_inicio
        self.hora_fin = hora_fin
        self.salon = salon

    def __repr__(self):
        return f'<Horario Docente:{self.docente_id} Dia:{self.dia_semana}>'

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    def to_dict(self):
        """Serializa la entrada del horario a dict."""
        return {
            'id': self.id,
            'docente_id': self.docente_id,
            'materia_id': self.materia_id,
            'materia': self.materia.nombre if self.materia else None,
            'dia_semana': self.dia_semana,
            'hora_inicio': self.hora_inicio.strftime('%H:%M') if self.hora_inicio else None,
            'hora_fin': self.hora_fin.strftime('%H:%M') if self.hora_fin else None,
            'salon': self.salon,
        }


class CalificacionMateria(db.Model):
    """Calificación por materia de un alumno.

    Modelo nuevo que relaciona directamente Alumno ↔ Materia con una
    calificación, permitiendo desacoplar las materias del esquema fijo
    de columnas que usa el modelo Calificacion original.
    """
    __tablename__ = 'calificaciones_materia'
    __table_args__ = {'schema': 'alejandra'}

    id = db.Column(db.Integer, primary_key=True)
    alumnos_id = db.Column(
        db.Integer,
        db.ForeignKey('alejandra.alumnos.id'),
        nullable=False
    )
    materia_id = db.Column(
        db.Integer,
        db.ForeignKey('alejandra.materias.id'),
        nullable=False
    )
    calificacion = db.Column(db.Numeric(5, 2), nullable=True)
    periodo = db.Column(db.String(50), nullable=True)  # ej: "1er Trimestre", "Ordinaria"
    creado_en = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # Relaciones
    alumno = db.relationship('Alumno', backref='calificaciones_materia')

    def __init__(self, alumnos_id, materia_id, calificacion=None, periodo=None):
        self.alumnos_id = alumnos_id
        self.materia_id = materia_id
        self.calificacion = calificacion
        self.periodo = periodo

    def __repr__(self):
        return f'<Calif Alumno:{self.alumnos_id} Mat:{self.materia_id} = {self.calificacion}>'

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    def to_dict(self):
        return {
            'id': self.id,
            'alumno_id': self.alumnos_id,
            'materia_id': self.materia_id,
            'materia': self.materia.nombre if self.materia else None,
            'calificacion': float(self.calificacion) if self.calificacion is not None else None,
            'periodo': self.periodo,
        }