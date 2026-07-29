import logging
import secrets
import string as string_module

from flask import abort, render_template, redirect, url_for, request, jsonify
from flask_login import current_user, login_required

from app.auth.models import Docente
from app.models import Alumno, Calificacion, Horario, Materia
from . import public_bp
from .forms import AlumnoEditForm, RegAlumnos

logger = logging.getLogger(__name__)


def _generar_codigo(longitud=10):
    """Genera un código alfanumérico aleatorio de 10 caracteres."""
    alfabeto = string_module.ascii_uppercase + string_module.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(longitud))


@public_bp.route("/")
def home():
    """Página de bienvenida pública con dos opciones: alumno/tutor o profesor."""
    return render_template("public/home.html")


@public_bp.route("/alumnos/")
@login_required
def index():
    alumnos = Alumno.query.order_by(Alumno.id.asc()).all()
    return render_template("public/index.html", alumno=alumnos)


@public_bp.route('/alumno/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_alumno():
    form = RegAlumnos()
    if form.validate_on_submit():
        # Generar código único de 10 dígitos
        codigo = _generar_codigo()
        while Alumno.query.filter_by(password=codigo).first():
            codigo = _generar_codigo()

        alumno = Alumno(
            name=form.name.data,
            lastname_p=form.lastname_p.data,
            lastname_m=form.lastname_m.data,
            group_id=form.group_id.data,
            genero=form.genero.data,
            password=codigo,
            status=True,
        )
        alumno.save()
        alumno.generate_qr_code(str(alumno.id))

        return redirect(url_for('public.index'))

    return render_template('public/nuevo_alumno.html', form=form)

@public_bp.route("/buscar/")
def buscar_alumno():
    """Página pública de búsqueda con input de código y escáner QR."""
    return render_template("public/alumn_search.html")


@public_bp.route("/calificaciones")
def calificaciones():
    codigo = request.args.get('codigoAlumno')
    alumno_encontrado = None
    materias_list = []

    if codigo:
        alumno_encontrado = Alumno.query.filter_by(password=codigo).first()
        if alumno_encontrado and alumno_encontrado.calificaciones:
            calif = alumno_encontrado.calificaciones[0]
            materias_list = [
                {'nombre': 'Español', 'nota': calif.español},
                {'nombre': 'Matemáticas', 'nota': calif.matematicas},
                {'nombre': 'Ciencias', 'nota': calif.ciencias},
                {'nombre': 'Geografía', 'nota': calif.geografia},
                {'nombre': 'Historia', 'nota': calif.historia},
                {'nombre': 'Formación Cívica y Ética', 'nota': calif.f_civica},
                {'nombre': 'Inglés', 'nota': calif.ingles},
                {'nombre': 'Artes', 'nota': calif.artes},
                {'nombre': 'Fortalecimiento de Español', 'nota': calif.f_español},
                {'nombre': 'Fortalecimiento de Matemáticas', 'nota': calif.f_matematicas},
                {'nombre': 'Tecnología', 'nota': calif.tecnologia},
            ]
    
    return render_template(
        "public/calificaciones.html",
        alumno=alumno_encontrado,
        materias=materias_list
    )


@public_bp.route('/api/alumno/register', methods=['POST'])
@login_required
def api_alumno_register():
    data = request.get_json(silent=True) or {}
    required_fields = ['name', 'lastname_p', 'lastname_m', 'group_id', 'genero']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Falta el campo {field}'}), 400

    codigo = _generar_codigo()
    while Alumno.query.filter_by(password=codigo).first():
        codigo = _generar_codigo()

    alumno = Alumno(
        name=data['name'],
        lastname_p=data['lastname_p'],
        lastname_m=data['lastname_m'],
        group_id=data['group_id'],
        genero=data['genero'],
        password=codigo,
        status=True,
    )
    alumno.save()
    alumno.generate_qr_code(str(alumno.id))

    return jsonify({'alumno': alumno.to_dict(), 'codigo': codigo}), 201


@public_bp.route('/api/alumno/<string:codigo>/calificaciones', methods=['GET'])
@login_required
def api_alumno_calificaciones(codigo):
    alumno = Alumno.find_by_code(codigo)
    if alumno is None:
        return jsonify({'error': 'Alumno no encontrado'}), 404

    materias = []
    if alumno.calificaciones_materia:
        materias = [c.to_dict() for c in alumno.calificaciones_materia]
    elif alumno.calificaciones:
        calif = alumno.calificaciones[0]
        materias = [
            {'nombre': 'Español', 'nota': calif.español},
            {'nombre': 'Matemáticas', 'nota': calif.matematicas},
            {'nombre': 'Ciencias', 'nota': calif.ciencias},
            {'nombre': 'Geografía', 'nota': calif.geografia},
            {'nombre': 'Historia', 'nota': calif.historia},
            {'nombre': 'Formación Cívica y Ética', 'nota': calif.f_civica},
            {'nombre': 'Inglés', 'nota': calif.ingles},
            {'nombre': 'Artes', 'nota': calif.artes},
            {'nombre': 'Fortalecimiento de Español', 'nota': calif.f_español},
            {'nombre': 'Fortalecimiento de Matemáticas', 'nota': calif.f_matematicas},
            {'nombre': 'Tecnología', 'nota': calif.tecnologia},
        ]

    return jsonify({
        'alumno': alumno.to_dict(),
        'materias': materias,
    })


@public_bp.route('/api/docente/<int:docente_id>/datos', methods=['GET'])
@login_required
def api_docente_datos(docente_id):
    docente = Docente.get_by_id(docente_id)
    if docente is None:
        return jsonify({'error': 'Docente no encontrado'}), 404

    if current_user.id != docente.id and not current_user.is_admin:
        return jsonify({'error': 'No autorizado'}), 403

    materias = [m.to_dict() for m in docente.materias.order_by(Materia.nombre).all()]
    horarios = [h.to_dict() for h in Horario.query.filter_by(docente_id=docente.id)
        .order_by(Horario.dia_semana, Horario.hora_inicio).all()]

    return jsonify({
        'docente_id': docente.id,
        'docente_nombre': f'{docente.nombre} {docente.apellidos}'.strip(),
        'materias': materias,
        'horario': horarios,
    })


@public_bp.route('/alumno/<int:alumno_id>/editar', methods=['GET', 'POST'])
@login_required
def edit_alumno(alumno_id):
    alumno = Alumno.query.get_or_404(alumno_id)
    form = AlumnoEditForm()

    if request.method == 'GET':
        form.name.data = alumno.name
        form.lastname_p.data = alumno.lastname_p
        form.lastname_m.data = alumno.lastname_m
        form.genero.data = alumno.genero
        form.group_id.data = alumno.group_id
        form.password.data = alumno.password
        form.status.data = alumno.status

        if alumno.calificaciones:
            calificacion = alumno.calificaciones[0]
            form.español.data = calificacion.español
            form.matematicas.data = calificacion.matematicas
            form.ciencias.data = calificacion.ciencias
            form.geografia.data = calificacion.geografia
            form.historia.data = calificacion.historia
            form.f_civica.data = calificacion.f_civica
            form.ingles.data = calificacion.ingles
            form.artes.data = calificacion.artes
            form.f_español.data = calificacion.f_español
            form.f_matematicas.data = calificacion.f_matematicas
            form.tecnologia.data = calificacion.tecnologia

    if form.validate_on_submit():
        alumno.name = form.name.data
        alumno.lastname_p = form.lastname_p.data
        alumno.lastname_m = form.lastname_m.data
        alumno.genero = form.genero.data
        alumno.group_id = form.group_id.data
        alumno.password = form.password.data
        alumno.status = form.status.data

        if alumno.calificaciones:
            calificacion = alumno.calificaciones[0]
        else:
            calificacion = Calificacion(alumnos_id=alumno.id)
            alumno.calificaciones.append(calificacion)

        calificacion.español = form.español.data
        calificacion.matematicas = form.matematicas.data
        calificacion.ciencias = form.ciencias.data
        calificacion.geografia = form.geografia.data
        calificacion.historia = form.historia.data
        calificacion.f_civica = form.f_civica.data
        calificacion.ingles = form.ingles.data
        calificacion.artes = form.artes.data
        calificacion.f_español = form.f_español.data
        calificacion.f_matematicas = form.f_matematicas.data
        calificacion.tecnologia = form.tecnologia.data

        alumno.save()
        calificacion.save()
        return redirect(url_for('public.index'))

    return render_template('public/edit_alumno.html', alumno=alumno, form=form)


@public_bp.route('/alumno/<int:alumno_id>/baja', methods=['POST'])
@login_required
def baja_alumno(alumno_id):
    alumno = Alumno.query.get_or_404(alumno_id)
    alumno.status = False
    alumno.save()
    return redirect(url_for('public.index'))


@public_bp.route("/docente/")
@login_required
def docente_panel():
    """
    Panel del docente autenticado.
    Muestra sus materias asignadas y su horario semanal.
    """
    docente = current_user
    materias = docente.materias.order_by(Materia.nombre).all()
    horarios = Horario.query\
        .filter_by(docente_id=docente.id)\
        .order_by(Horario.dia_semana, Horario.hora_inicio)\
        .all()
    return render_template(
        'public/docente.html',
        docente=docente,
        materias=materias,
        horarios=horarios
    )


@public_bp.route("/api/docente/<int:docente_id>/materias")
@login_required
def api_docente_materias(docente_id):
    """
    API: Devuelve las materias asignadas a un docente.
    ---
    Solo el propio docente o un admin pueden consultar.
    """
    docente = Docente.get_by_id(docente_id)
    if docente is None:
        return jsonify({'error': 'Docente no encontrado'}), 404

    # Solo el propio docente o un admin puede ver sus materias
    if current_user.id != docente.id and not current_user.is_admin:
        return jsonify({'error': 'No autorizado'}), 403

    materias = docente.materias.order_by(Materia.nombre).all()
    return jsonify({
        'docente_id': docente.id,
        'docente_nombre': f'{docente.nombre} {docente.apellidos}'.strip(),
        'materias': [
            {
                'id': m.id,
                'nombre': m.nombre,
                'descripcion': m.descripcion,
            }
            for m in materias
        ]
    })


@public_bp.route("/api/docente/<int:docente_id>/horario")
@login_required
def api_docente_horario(docente_id):
    """
    API: Devuelve el horario semanal de un docente.
    ---
    Agrupado por día de la semana (1=Lunes … 5=Viernes).
    """
    docente = Docente.get_by_id(docente_id)
    if docente is None:
        return jsonify({'error': 'Docente no encontrado'}), 404

    if current_user.id != docente.id and not current_user.is_admin:
        return jsonify({'error': 'No autorizado'}), 403

    horarios = Horario.query.filter_by(docente_id=docente_id)\
        .order_by(Horario.dia_semana, Horario.hora_inicio).all()

    DIAS = ['', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

    agrupado = {}
    for h in horarios:
        dia_nombre = DIAS[h.dia_semana] if 1 <= h.dia_semana <= 7 else f'Día {h.dia_semana}'
        if dia_nombre not in agrupado:
            agrupado[dia_nombre] = []
        agrupado[dia_nombre].append(h.to_dict())

    return jsonify({
        'docente_id': docente.id,
        'docente_nombre': f'{docente.nombre} {docente.apellidos}'.strip(),
        'horario': agrupado
    })


@public_bp.route("/error")
@login_required
def show_error():
    res = 1 / 0
    return "Error"
