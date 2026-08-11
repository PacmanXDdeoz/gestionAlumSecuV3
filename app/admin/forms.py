from flask_wtf import FlaskForm
from wtforms import (BooleanField, PasswordField, SelectField, SelectMultipleField,
                     StringField, SubmitField)
from wtforms.validators import DataRequired, Email, Length, Optional

from app.auth.models import Docente, Rol
from app.models import Grupos, Materia


GRADOS_CHOICES = [(str(i), f'{i}°') for i in range(1, 7)]
GRUPOS_CHOICES = [(chr(l), chr(l)) for l in range(ord('A'), ord('F') + 1)]

DIAS_CHOICES = [
    (str(i), nombre)
    for i, nombre in enumerate(
        ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'],
        start=1,
    )
]

# Etiquetas legibles para los roles del catálogo, indexadas por id
# (1=admin, 2=docente). Las opciones se leen de la tabla alejandra.rol.
_ROL_LABELS = {
    1: 'Administrador',
    2: 'Docente',
}


def _rol_choices():
    """Retorna las opciones de rol desde el catálogo de la BD (id, etiqueta).

    Si el catálogo no existe o está vacío, degrada a los valores por defecto
    (1=admin, 2=docente) para no romper el formulario.
    """
    roles = Rol.get_all()
    if not roles:
        roles_ids = (1, 2)
    else:
        roles_ids = [r.id for r in roles]
    return [(rid, _ROL_LABELS.get(rid, f'Rol {rid}')) for rid in roles_ids]

def _materia_choices():
    """Retorna las opciones de materias desde la BD."""
    materias = Materia.query.order_by(Materia.nombre).all()
    return [(str(m.id), m.nombre) for m in materias]


def _grupo_choices():
    """Retorna las opciones de grupos desde la BD."""
    grupos = Grupos.query.order_by(Grupos.grado, Grupos.grupo).all()
    return [(str(g.id), f'{g.grado}° {g.grupo}') for g in grupos]


class DocenteAdminForm(FlaskForm):
    name = StringField('Nombre(s)', validators=[DataRequired(), Length(max=64)])
    apellidos = StringField('Apellidos', validators=[Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[Optional(), Length(min=4, max=128)])
    rol = SelectField('Rol', choices=[], coerce=int, validators=[DataRequired()])
    materias = SelectMultipleField('Materias asignadas', choices=[], coerce=int)
    submit = SubmitField('Guardar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.materias.choices = _materia_choices()
        self.rol.choices = _rol_choices()


class AlumnoAdminForm(FlaskForm):
    name = StringField('Nombre(s)', validators=[DataRequired(), Length(max=50)])
    lastname_p = StringField('Apellido Paterno', validators=[DataRequired(), Length(max=50)])
    lastname_m = StringField('Apellido Materno', validators=[DataRequired(), Length(max=50)])
    genero = SelectField('Género', choices=[('M', 'Masculino'), ('F', 'Femenino'), ('Otro', 'Otro')],
                         validators=[DataRequired()])
    group_id = SelectField('Grupo', choices=[], coerce=int, validators=[DataRequired()])
    codigo_manual = StringField('Código (opcional)', validators=[Optional(), Length(max=10)])
    auto_generar_codigo = BooleanField('Generar código automáticamente', default=True)
    submit = SubmitField('Registrar Alumno')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_id.choices = _grupo_choices()


class GrupoForm(FlaskForm):
    grado = SelectField('Grado', choices=GRADOS_CHOICES, validators=[DataRequired()])
    grupo = SelectField('Grupo', choices=GRUPOS_CHOICES, validators=[DataRequired()])
    submit = SubmitField('Guardar grupo')


class GrupoMateriasForm(FlaskForm):
    """Asigna las materias (currículum) que se imparten en un grupo."""
    materias = SelectMultipleField('Materias del grupo', choices=[], coerce=int)
    submit = SubmitField('Guardar materias')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.materias.choices = _materia_choices()


def _docente_choices():
    """Retorna las opciones de docentes desde la BD."""
    docentes = Docente.query.order_by(Docente.nombre).all()
    return [(str(d.id), f'{d.nombre} {d.apellidos}'.strip()) for d in docentes]


class HorarioAdminForm(FlaskForm):
    """Alta/edición de una entrada del horario de un docente.

    Cada entrada liga docente + materia + grupo (el grupo donde imparte
    esa materia) con un día y un horario. El grupo es la fuente de verdad
    para que el docente solo vea a los alumnos de sus grupos.
    """
    docente_id = SelectField('Docente', choices=[], coerce=int, validators=[DataRequired()])
    materia_id = SelectField('Materia', choices=[], coerce=int, validators=[DataRequired()])
    grupo_id = SelectField('Grupo', choices=[(0, '— Sin grupo —')], coerce=int, validators=[DataRequired()])
    dia_semana = SelectField('Día', choices=DIAS_CHOICES, coerce=int, validators=[DataRequired()])
    # type="time": el navegador muestra el selector de reloj nativo y envía
    # el valor como HH:MM (o HH:MM:SS según el step). El backend los parsea
    # con _parse_hora (acepta ambos formatos).
    hora_inicio = StringField('Hora de inicio', validators=[DataRequired()],
                              render_kw={'type': 'time'})
    hora_fin = StringField('Hora de fin', validators=[DataRequired()],
                           render_kw={'type': 'time'})
    salon = StringField('Salón', validators=[Optional(), Length(max=20)])
    submit = SubmitField('Guardar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.docente_id.choices = _docente_choices()
        self.materia_id.choices = _materia_choices()
        self.grupo_id.choices = [(0, '— Sin grupo —')] + _grupo_choices()
