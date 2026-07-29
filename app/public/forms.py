from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length

from app.models import Grupos


def _grupo_choices():
    """Retorna las opciones de grupos desde la BD."""
    grupos = Grupos.query.order_by(Grupos.grado, Grupos.grupo).all()
    return [(str(g.id), f'{g.grado}° {g.grupo}') for g in grupos]


class RegAlumnos(FlaskForm):
    name = StringField('Nombre(s)', validators=[DataRequired(), Length(max=50)])
    lastname_p = StringField('Apellido Paterno', validators=[DataRequired(), Length(max=50)])
    lastname_m = StringField('Apellido Materno', validators=[DataRequired(), Length(max=50)])
    genero = SelectField('Género', choices=[('M', 'Masculino'), ('F', 'Femenino'), ('Otro', 'Otro')], validators=[DataRequired()])
    group_id = SelectField('Grupo', choices=[], coerce=int, validators=[DataRequired()])
    submit = SubmitField('Registrar Alumno')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_id.choices = _grupo_choices()


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