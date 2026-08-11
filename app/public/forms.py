from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.auth.models import Docente
from app.models import Grupos


def _grupo_choices():
    """Retorna las opciones de grupos desde la BD."""
    grupos = Grupos.query.order_by(Grupos.grado, Grupos.grupo).all()
    return [(str(g.id), f'{g.grado}° {g.grupo}') for g in grupos]


def _docente_choices(tutor_actual_id=None):
    """Retorna las opciones de docentes (id, 'Nombre Apellidos').

    Solo docentes activos (``estatus=True``), salvo el tutor ya asignado al
    alumno (``tutor_actual_id``): aunque ese docente esté desactivado, se
    incluye para que el select conserve la asignación actual y no se borre
    silenciosamente al guardar sin tocar el campo.
    """
    docentes = Docente.query\
        .filter_by(estatus=True)\
        .order_by(Docente.nombre, Docente.apellidos)\
        .all()
    opciones = [
        (str(d.id), f'{d.nombre} {d.apellidos}'.strip())
        for d in docentes
    ]

    # El tutor actual puede estar desactivado: asegurar que siga en la lista.
    if tutor_actual_id:
        ids = {int(doc_id) for doc_id, _ in opciones}
        if int(tutor_actual_id) not in ids:
            tutor = Docente.get_by_id(int(tutor_actual_id))
            if tutor is not None:
                opciones.insert(1, (str(tutor.id), f'{tutor.nombre} {tutor.apellidos}'.strip()))
    return opciones


class RegAlumnos(FlaskForm):
    name = StringField('Nombre(s)', validators=[DataRequired(), Length(max=50)])
    lastname_p = StringField('Apellido Paterno', validators=[DataRequired(), Length(max=50)])
    lastname_m = StringField('Apellido Materno', validators=[DataRequired(), Length(max=50)])
    genero = SelectField('Género', choices=[('M', 'Masculino'), ('F', 'Femenino'), ('Otro', 'Otro')], validators=[DataRequired()])
    group_id = SelectField('Grupo', choices=[], coerce=int, validators=[DataRequired()])
    submit = SubmitField('Registrar alumno(s)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_id.choices = _grupo_choices()


class DocenteEditAlumnoForm(FlaskForm):
    """Edición de los datos de identidad de un alumno desde el panel docente.

    Es deliberadamente más ligero que ``AlumnoEditForm``: solo los campos de
    información que se muestran en la tarjeta del alumno (nombre, apellidos,
    género, grupo y código). El estatus y las calificaciones se gestionan
    por sus propios flujos (admin / roster).
    """
    name = StringField('Nombre(s)', validators=[DataRequired(), Length(max=50)])
    lastname_p = StringField('Apellido Paterno', validators=[DataRequired(), Length(max=50)])
    lastname_m = StringField('Apellido Materno', validators=[DataRequired(), Length(max=50)])
    genero = SelectField('Género', choices=[('M', 'Masculino'), ('F', 'Femenino'), ('Otro', 'Otro')], validators=[DataRequired()])
    group_id = SelectField('Grupo', choices=[], coerce=int, validators=[DataRequired()])
    password = StringField('Código de alumno', validators=[DataRequired(), Length(max=10)])
    tutor_id = SelectField('Profesor', choices=[], coerce=int, validators=[Optional()])
    # Calificación: la materia se limita a las disponibles para el usuario
    # (anti-IDOR: el docente solo las que imparte; el admin todas).
    materia_id = SelectField('Materia', choices=[], coerce=int, validators=[Optional()])
    calificacion = FloatField('Calificación (0–10)',
                              validators=[Optional(), NumberRange(min=0, max=10)])
    # Nota/comentario que el docente comparte con el alumno para la materia
    # seleccionada. Opcional: puede dejarse vacía (borra la nota anterior).
    nota_texto = TextAreaField('Nota para el alumno',
                               validators=[Optional(), Length(max=2000)])
    submit = SubmitField('Guardar cambios')

    def __init__(self, *args, tutor_actual_id=None, materias_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_id.choices = _grupo_choices()
        self.tutor_id.choices = [(0, '— Sin asignar —')] + _docente_choices(tutor_actual_id)
        self.materia_id.choices = materias_choices or []


class AlumnoEditForm(FlaskForm):
    name = StringField('Nombre', validators=[DataRequired(), Length(max=50)])
    lastname_p = StringField('Apellido paterno', validators=[DataRequired(), Length(max=50)])
    lastname_m = StringField('Apellido materno', validators=[DataRequired(), Length(max=50)])
    genero = SelectField('Género', choices=[('M', 'Masculino'), ('F', 'Femenino'), ('Otro', 'Otro')], validators=[DataRequired()])
    group_id = SelectField('Grupo', choices=[], coerce=int, validators=[DataRequired()])
    password = StringField('Código', validators=[DataRequired(), Length(max=10)])
    status = BooleanField('Activo')
    español = FloatField('Español')
    matematicas = FloatField('Matemáticas')
    ciencias = FloatField('Ciencias')
    geografia = FloatField('Geografia')
    historia = FloatField('Historia')
    f_civica = FloatField('Formación Cívica')
    ingles = FloatField('Inglés')
    artes = FloatField('Artes')
    f_español = FloatField('Fortalecimiento Español')
    f_matematicas = FloatField('Fortalecimiento Matemáticas')
    tecnologia = FloatField('Tecnología')
    submit = SubmitField('Guardar cambios')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_id.choices = _grupo_choices()