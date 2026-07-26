from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, IntegerField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length


class RegAlumnos(FlaskForm):
    name = StringField('Nombre(s)', validators=[DataRequired(), Length(max=50)])
    lastname_p = StringField('Apellido Paterno', validators=[DataRequired(), Length(max=50)])
    lastname_m = StringField('Apellido Materno', validators=[DataRequired(), Length(max=50)])
    genero = SelectField('Género', choices=[('M', 'Masculino'), ('F', 'Femenino'), ('Otro', 'Otro')], validators=[DataRequired()])
    group_id = IntegerField('ID del Grupo', validators=[DataRequired()])
    password = StringField('Código', validators=[DataRequired(), Length(max=10)])
    status = BooleanField('Activo')
    submit = SubmitField('Registrar Alumno')


class AlumnoEditForm(FlaskForm):
    name = StringField('Nombre', validators=[DataRequired(), Length(max=50)])
    lastname_p = StringField('Apellido paterno', validators=[DataRequired(), Length(max=50)])
    lastname_m = StringField('Apellido materno', validators=[DataRequired(), Length(max=50)])
    genero = SelectField('Género', choices=[('M', 'Masculino'), ('F', 'Femenino'), ('Otro', 'Otro')], validators=[DataRequired()])
    group_id = IntegerField('Grupo', validators=[DataRequired()])
    password = StringField('Código', validators=[DataRequired(), Length(max=10)])
    status = BooleanField('Activo')
    español = FloatField('Español')
    matematicas = FloatField('Matemáticas')
    ciencias = FloatField('Ciencias')
    geografia = FloatField('Geografía')
    historia = FloatField('Historia')
    f_civica = FloatField('Formación Cívica')
    ingles = FloatField('Inglés')
    artes = FloatField('Artes')
    f_español = FloatField('Fortalecimiento Español')
    f_matematicas = FloatField('Fortalecimiento Matemáticas')
    tecnologia = FloatField('Tecnología')
    submit = SubmitField('Guardar cambios')