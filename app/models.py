import datetime

from sqlalchemy.exc import ProgrammingError

from app import db


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

# ──────────────────────────────────────────────
#  TABLA DE ASOCIACIÓN: Grupo ↔ Materia
#  (define el currículum: qué materias se imparten en cada grupo)
# ──────────────────────────────────────────────
grupos_materias = db.Table(
    'grupos_materias',
    db.Model.metadata,
    db.Column('grupo_id', db.Integer, db.ForeignKey('alejandra.grupos.id'), primary_key=True),
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
    grupos = db.relationship('Grupos', secondary=grupos_materias, back_populates='materias', lazy='dynamic')
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
        for nombre, desc in MATERIAS_DEFAULT:
            if not Materia.query.filter_by(nombre=nombre).first():
                db.session.add(Materia(nombre=nombre, descripcion=desc))
        db.session.commit()


# Materias por defecto del plantel (usadas por seed_materias y por la
# migración de seed). Se mantienen aquí como fuente única para tests.
MATERIAS_DEFAULT = [
    ('Español', 'Lengua y literatura'),
    ('Matemáticas', 'Matemáticas'),
    ('Biología', 'Biología'),
    ('Química', 'Química'),
    ('Física', 'Física'),
    ('Historia', 'Historia'),
    ('Formación cívica y Ética', 'Formación cívica y Ética'),
    ('Geografía', 'Geografía'),
    ('Inglés', 'Inglés'),
    ('Artes (música y teatro)', 'Artes: música y teatro'),
    ('Tecnologías (talleres)', 'Tecnologías: talleres'),
    ('Fomento a la lectura', 'Fomento a la lectura'),
    ('Educación Física', 'Educación Física'),
]


class Grupos(db.Model):
    __tablename__='grupos'
    __table_args__ = {'schema': 'alejandra'}
    id = db.Column(db.Integer, primary_key=True)
    grado = db.Column(db.String(1), nullable=False)
    grupo = db.Column(db.String(1), nullable=False)

    alumnos = db.relationship('Alumno', backref='grupo_info', lazy=True)
    materias = db.relationship('Materia', secondary=grupos_materias, back_populates='grupos', lazy='dynamic')

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
    # Profesor/tutor asignado al alumno (nullable: opcional).
    tutor_id = db.Column(db.Integer, db.ForeignKey('alejandra.docentes.id'), nullable=True)

    calificaciones = db.relationship('Calificacion', backref='alumno', lazy=True)
    anotaciones = db.relationship('AnotacionAlumno', backref='alumno', lazy=True)
    tutor = db.relationship('Docente', foreign_keys=[tutor_id], backref='alumnos_tutoreados')

    def __init__(self, name, lastname_p, lastname_m, group_id, genero, password, status=True, tutor_id=None):
        self.name = name
        self.lastname_p = lastname_p
        self.lastname_m = lastname_m
        self.group_id = group_id
        self.genero = genero
        self.status = status
        self.password = password
        self.tutor_id = tutor_id

    def __repr__(self):
        return f'<Alumno {self.name} {self.lastname_p}>'

    @property
    def full_name(self):
        return ' '.join(part for part in [self.name, self.lastname_p, self.lastname_m] if part)

    @staticmethod
    def find_by_code(code):
        return Alumno.query.filter_by(password=code).first()

    @staticmethod
    def find_by_code_or_id(code):
        """Busca un alumno por código de acceso o, si el valor es numérico, por ID.

        Los códigos QR del sistema no son uniformes: los alumnos creados por
        las rutas públicas codifican el ID numérico (``str(alumno.id)``),
        mientras que los creados desde el panel admin codifican el código de
        acceso (``password``). Este método permite que el escáner QR y el
        buscador resuelvan ambos casos.
        """
        alumno = Alumno.query.filter_by(password=code).first()
        if alumno is not None:
            return alumno
        if code and str(code).isdigit():
            return db.session.get(Alumno, int(code))
        return None

    def generate_qr_code(self, texto=None):
        from flask import current_app, url_for

        from app.utils.qr import generar_qr, qr_codes_folder

        if texto is None:
            # El QR codifica la URL absoluta de la boleta pública del alumno
            # (escaneo nativo): al escanear la credencial con la cámara del
            # celular se abre directamente la vista del alumno, sin necesidad
            # de librerías JS de escaneo en /buscar/.
            #
            # El dominio con el que se guardan los QRs se controla desde
            # PUBLIC_BASE_URL en .env: si está definido (p. ej.
            # http://192.168.100.8:5000 en testeo), se usa SIEMPRE, incluso
            # dentro de un request (es determinista e independiente del host
            # de la petición). Si está vacío, se usa el host de la petición
            # (url_for(_external=True)) o, fuera de request (p. ej. el
            # comando ``flask regenerate-qrs``), se lanza un error.
            base = current_app.config.get('PUBLIC_BASE_URL', '').strip()
            if base:
                texto = f'{base.rstrip("/")}/buscar/{self.id}'
            else:
                try:
                    texto = url_for('public.boleta_alumno', id=self.id, _external=True)
                except RuntimeError:
                    raise RuntimeError(
                        'No hay contexto de request y PUBLIC_BASE_URL no está '
                        'configurado (defínelo en .env) para generar la URL '
                        'absoluta del QR.'
                    )

        # Carpeta de QRs configurable (fuente única: app.utils.qr.qr_codes_folder).
        # El entorno de testing la redirige a un directorio temporal para que
        # la suite no escriba PNGs de alumnos de prueba sobre la carpeta real
        # (parecerían QRs de alumnos ya eliminados de la BD); en producción
        # usa la carpeta estándar <static>/qrcodes.
        self.codigo_qr = generar_qr(texto, qr_codes_folder(), f'alumno_{self.id}.png')
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


class AnotacionAlumno(db.Model):
    __tablename__ = 'anotaciones_alumno'
    __table_args__ = {'schema': 'alejandra'}

    id = db.Column(db.Integer, primary_key=True)
    alumno_id = db.Column(db.Integer, db.ForeignKey('alejandra.alumnos.id'), nullable=False)
    docente_id = db.Column(db.Integer, db.ForeignKey('alejandra.docentes.id'), nullable=True)
    texto = db.Column(db.Text, nullable=False, default='')
    creado_en = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    docente = db.relationship('Docente', backref='anotaciones_alumno')

    def __init__(self, alumno_id, texto='', docente_id=None):
        self.alumno_id = alumno_id
        self.texto = texto
        self.docente_id = docente_id

    def save(self):
        if not self.id:
            db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @staticmethod
    def get_by_alumno(alumno_id):
        try:
            return AnotacionAlumno.query.filter_by(alumno_id=alumno_id).first()
        except ProgrammingError:
            return None


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
    una materia, el grupo donde se imparte y un salón, asignados a un
    docente específico. El grupo (``grupo_id``) es la fuente de verdad
    para saber qué alumnos corresponden a cada docente.
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
    grupo_id = db.Column(
        db.Integer,
        db.ForeignKey('alejandra.grupos.id'),
        nullable=True
    )
    dia_semana = db.Column(db.Integer, nullable=False)  # 1=Lunes … 7=Domingo
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    salon = db.Column(db.String(20), nullable=True)

    # Relación backref: docente desde Docente, materia desde Materia,
    # grupo desde Grupos (lazy para evitar N+1 en el panel; precargar con
    # joinedload(Horario.grupo) en _horarios_de_docente).
    grupo = db.relationship('Grupos', backref='horarios', lazy=True)

    def __init__(self, docente_id, materia_id, dia_semana, hora_inicio, hora_fin, salon=None, grupo_id=None):
        self.docente_id = docente_id
        self.materia_id = materia_id
        self.dia_semana = dia_semana
        self.hora_inicio = hora_inicio
        self.hora_fin = hora_fin
        self.salon = salon
        self.grupo_id = grupo_id

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
            'grupo_id': self.grupo_id,
            'grupo': f"{self.grupo.grado}° {self.grupo.grupo}" if self.grupo else None,
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
    # Nota/comentario que el docente comparte con el alumno para esta materia.
    # Una por (alumno, materia): la boleta la muestra junto a la calificación.
    nota_texto = db.Column(db.Text, nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # Relaciones
    alumno = db.relationship('Alumno', backref='calificaciones_materia')

    def __init__(self, alumnos_id, materia_id, calificacion=None, periodo=None, nota_texto=None):
        self.alumnos_id = alumnos_id
        self.materia_id = materia_id
        self.calificacion = calificacion
        self.periodo = periodo
        self.nota_texto = nota_texto

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
            'nota_texto': self.nota_texto,
            'periodo': self.periodo,
        }