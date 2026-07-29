from flask_wtf import FlaskForm
from wtforms import (BooleanField, PasswordField, SelectField, SelectMultipleField,
                     StringField, SubmitField)
from wtforms.validators import DataRequired, Email, Length, Optional

from app.models import Grupos, Materia


GRADOS_CHOICES = [(str(i), f'{i}°') for i in range(1, 7)]
GRUPOS_CHOICES = [(chr(l), chr(l)) for l in range(ord('A'), ord('F') + 1)]


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
    rol = SelectField('Rol', choices=[('docente', 'Docente'), ('admin', 'Administrador')],
                      validators=[DataRequired()])
    materias = SelectMultipleField('Materias asignadas', choices=[], coerce=int)
    submit = SubmitField('Guardar')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.materias.choices = _materia_choices()


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
