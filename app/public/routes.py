import logging
from pathlib import Path

from flask import (
    abort,
    flash,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
    send_file,
    send_from_directory,
)
from flask_login import current_user, login_required

from sqlalchemy.orm import joinedload, selectinload

from app import db
from app.auth.models import Docente, Rol, es_admin
from app.models import (
    Alumno,
    Calificacion,
    Grupos,
    Horario,
    Materia,
    CalificacionMateria,
    MATERIAS_DEFAULT,
)
from app.utils.codes import generar_codigo
from app.utils.pdf import generar_imagen_qr, generar_pdf_qr
from . import public_bp
from .forms import AlumnoEditForm, DocenteEditAlumnoForm, RegAlumnos

logger = logging.getLogger(__name__)

# Nombre de materia → columna del modelo Calificacion (esquema fijo).
# Solo las materias del catálogo actual (MATERIAS_DEFAULT) que tienen columna
# equivalente en el esquema fijo. Las materias sin columna (Biología, Química,
# Física, Fomento a la lectura, Educación Física) se guardan en
# CalificacionMateria (ver _get_nota_materia / _set_nota_materia).
MATERIA_COLUMNS_MAP = {
    'Español': 'español',
    'Matemáticas': 'matematicas',
    'Historia': 'historia',
    'Formación cívica y Ética': 'f_civica',
    'Geografía': 'geografia',
    'Inglés': 'ingles',
    'Artes (música y teatro)': 'artes',
    'Tecnologías (talleres)': 'tecnologia',
}


def ensure_required_tables():
    """Creates missing app tables defensively to avoid silent save failures."""
    try:
        db.create_all()
        Rol.seed_defaults()
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning('No se pudieron crear tablas automáticamente: %s', exc)
        raise


def _docente_imparte_materia(docente, materia_nombre):
    """¿El docente tiene asignada la materia indicada (por nombre)?"""
    if not materia_nombre:
        return False
    materias = getattr(docente, 'materias', None)
    if materias is None:
        return False
    return materias.filter_by(nombre=materia_nombre).first() is not None


def _docente_imparte_materias_del_alumno(docente, alumno):
    """¿El docente imparte al menos una materia que corresponda al alumno?

    Regla anti-IDOR para las vistas de edición y descarga de PDF:

    - Si el grupo del alumno tiene currículum configurado (``grupos_materias``),
      el docente debe impartir al menos una de esas materias.
    - Si el grupo no tiene currículum, se aplica el catálogo completo por
      defecto (igual que en la boleta) y basta con que el docente imparta
      cualquier materia.

    Los administradores no pasan por aquí: tienen acceso total (ver
    ``es_admin`` en las rutas que usan esta función).
    """
    grupo = alumno.grupo_info
    if grupo is None:
        return False

    materias_docente = {m.nombre for m in docente.materias.all()}
    if not materias_docente:
        return False

    materias_grupo = grupo.materias.all()
    if materias_grupo:
        nombres_grupo = {m.nombre for m in materias_grupo}
        return bool(materias_docente & nombres_grupo)
    return True


def _get_nota_materia(alumno, materia_nombre):
    """Lee la nota de una materia para la boleta/roster.

    Prioridad: un registro explícito de ``CalificacionMateria`` **con
    calificación** si existe; si no, la columna fija del esquema
    ``Calificacion`` (solo para materias incluidas en ``MATERIA_COLUMNS_MAP``).
    Las materias del catálogo sin columna fija (Biología, Química, Física, …)
    solo tienen nota si se registraron vía ``CalificacionMateria``.

    Un registro de ``CalificacionMateria`` con ``calificacion=None`` (p. ej.
    creado solo para guardar una nota de texto) NO tapa la calificación de la
    columna fija: se continúa al respaldo.
    """
    for cm in alumno.calificaciones_materia:
        if cm.materia and cm.materia.nombre == materia_nombre and cm.calificacion is not None:
            return float(cm.calificacion)

    m_col = MATERIA_COLUMNS_MAP.get(materia_nombre)
    if m_col:
        calif = alumno.calificaciones[0] if alumno.calificaciones else None
        valor = getattr(calif, m_col, None) if calif is not None else None
        return float(valor) if valor is not None else None
    return None


def _get_nota_texto_materia(alumno, materia_nombre):
    """Lee la nota/comentario del docente para una materia de la boleta.

    Devuelve el texto (o cadena vacía) del ``CalificacionMateria`` del par
    (alumno, materia). Es un campo independiente de la calificación: un
    docente puede compartir una observación aunque la nota numérica viva en
    la columna fija del esquema.
    """
    for cm in alumno.calificaciones_materia:
        if cm.materia and cm.materia.nombre == materia_nombre:
            return cm.nota_texto or ''
    return ''


def _set_nota_texto_materia(alumno, materia_nombre, texto):
    """Guarda la nota/comentario del docente para una materia.

    Reutiliza (o crea) el registro ``CalificacionMateria`` del par
    (alumno, materia). Un texto vacío borra la nota (None). No toca la
    calificación numérica de ese registro ni las columnas fijas.
    """
    texto = (texto or '').strip()
    materia = Materia.query.filter_by(nombre=materia_nombre).first()
    if materia is None:
        return
    cm = CalificacionMateria.query.filter_by(
        alumnos_id=alumno.id, materia_id=materia.id
    ).first()
    if cm is None:
        # Sin nota previa y sin texto nuevo: no crear registros vacíos.
        if not texto:
            return
        cm = CalificacionMateria(alumnos_id=alumno.id, materia_id=materia.id)
        db.session.add(cm)
    cm.nota_texto = texto or None


def _set_nota_materia(alumno, materia_nombre, valor):
    """Guarda la nota de una materia sin perder datos silenciosamente.

    - Si la materia ya tiene un registro ``CalificacionMateria``, se actualiza.
    - Si la materia está en ``MATERIA_COLUMNS_MAP``, se escribe en su columna
      fija del esquema ``Calificacion``.
    - Si no, se crea/actualiza un ``CalificacionMateria`` (materias nuevas
      sin columna fija: Biología, Química, Física, Fomento a la lectura,
      Educación Física).
    """
    valor_norm = float(valor) if valor is not None and valor != '' else None

    materia = Materia.query.filter_by(nombre=materia_nombre).first()
    if materia is not None:
        cm = CalificacionMateria.query.filter_by(
            alumnos_id=alumno.id, materia_id=materia.id
        ).first()
        if cm is not None:
            cm.calificacion = valor_norm
            return

    m_col = MATERIA_COLUMNS_MAP.get(materia_nombre)
    if m_col:
        calif = alumno.calificaciones[0] if alumno.calificaciones else None
        if calif is None:
            calif = Calificacion(alumnos_id=alumno.id)
            alumno.calificaciones.append(calif)
        setattr(calif, m_col, valor_norm)
        return

    if materia is not None:
        db.session.add(
            CalificacionMateria(
                alumnos_id=alumno.id,
                materia_id=materia.id,
                calificacion=valor_norm,
            )
        )


def _grupos_con_materia(materia):
    """IDs de los grupos cuyo currículum incluye la materia indicada.

    Devuelve ``None`` si ningún grupo tiene la materia asignada (currículum
    sin configurar) para conservar el comportamiento anterior de mostrar
    todos los alumnos; si ya hay currículum, devuelve los ids de los grupos
    que imparten la materia para filtrar el roster.
    """
    grupos_ids = [g.id for g in materia.grupos.all()]
    return grupos_ids or None


def _grupos_docente_para_materia(docente_id, materia_id):
    """Grupos donde el docente imparte la materia según su horario.

    Fuente de verdad de la asignación docente → grupo (columna
    ``horarios.grupo_id``). Devuelve una lista (posiblemente vacía): sin
    horario asignado, el docente no tiene grupos para esa materia.
    """
    filas = Horario.query\
        .filter_by(docente_id=docente_id, materia_id=materia_id)\
        .with_entities(Horario.grupo_id)\
        .distinct()\
        .all()
    return [gid for (gid,) in filas if gid is not None]


def _grupo_tiene_curriculum(alumno):
    """¿El grupo del alumno tiene un currículum configurado (``grupos_materias``)?

    Cuando es ``True``, la boleta muestra únicamente las materias del grupo
    y se muestra un aviso informativo al visitante.
    """
    grupo = alumno.grupo_info
    if grupo is None:
        return False
    return grupo.materias.first() is not None


def _materias_alumno(alumno):
    """Lista de materias ``{nombre, nota}`` para la boleta de un alumno.

    Si el grupo del alumno tiene un currículum configurado (``grupos_materias``),
    la boleta muestra únicamente las materias de ese grupo; si no está
    configurado, muestra el catálogo completo por defecto (``MATERIAS_DEFAULT``).
    Las notas se leen con ``_get_nota_materia`` (CalificacionMateria con
    prioridad, columna fija del esquema ``Calificacion`` como respaldo).
    """
    grupo = alumno.grupo_info
    materias_grupo = grupo.materias.order_by(Materia.id).all() if grupo is not None else []

    if materias_grupo:
        # ── Currículum del grupo: solo las materias asignadas al grupo ──
        return [
            {
                'nombre': m.nombre,
                'nota': _get_nota_materia(alumno, m.nombre),
                'nota_texto': _get_nota_texto_materia(alumno, m.nombre),
            }
            for m in materias_grupo
        ]

    # ── Sin currículum configurado: catálogo completo por defecto ──
    return [
        {
            'nombre': nombre,
            'nota': _get_nota_materia(alumno, nombre),
            'nota_texto': _get_nota_texto_materia(alumno, nombre),
        }
        for nombre, _ in MATERIAS_DEFAULT
    ]


def _docentes_por_materia_grupo(alumno):
    """Docentes que imparten cada materia al grupo del alumno (vía horario).

    Devuelve ``{nombre_materia: [nombres de docentes]}``. Fuente de verdad:
    la tabla ``horarios`` (docente_id + materia_id + grupo_id). Una sola
    consulta con ``joinedload`` de materia y docente (evita N+1). Un docente
    puede tener varias horas de la misma materia en el grupo: se deduplican.
    """
    grupo = alumno.grupo_info
    if grupo is None:
        return {}
    filas = (
        Horario.query
        .options(joinedload(Horario.materia), joinedload(Horario.docente))
        .filter_by(grupo_id=grupo.id)
        .all()
    )
    mapa = {}
    for h in filas:
        if h.materia is None or h.docente is None:
            continue
        # Prefijo 'Prof.' para mantener la consistencia con el resto de la
        # UI (tarjeta de tutor, vista de edición).
        nombre_docente = f'Prof. {h.docente.nombre} {h.docente.apellidos}'.strip()
        mapa.setdefault(h.materia.nombre, []).append(nombre_docente)
    return {nombre: list(dict.fromkeys(docentes)) for nombre, docentes in mapa.items()}


def _materias_boleta(alumno):
    """Materias de la boleta con su nota y los docentes que las imparten.

    Combina ``_materias_alumno`` (nombre + nota, según el currículum del
    grupo) con ``_docentes_por_materia_grupo`` (docentes que imparten cada
    materia al grupo del alumno según su horario).
    """
    materias = _materias_alumno(alumno)
    docentes_map = _docentes_por_materia_grupo(alumno)
    for m in materias:
        m['docentes'] = docentes_map.get(m['nombre'], [])
    return materias


def _horarios_de_docente(docente_id):
    """Horarios de un docente con materia y grupo precargados (evita N+1).

    ``Horario.to_dict()`` accede a ``self.materia.nombre`` y la plantilla
    del panel a ``h.grupo.grado``; sin los ``joinedload`` se dispararía
    1 query por horario.
    """
    return Horario.query\
        .options(joinedload(Horario.materia), joinedload(Horario.grupo))\
        .filter_by(docente_id=docente_id)\
        .order_by(Horario.dia_semana, Horario.hora_inicio)\
        .all()


def _alumnos_ordenados_con_cargas():
    """Query base de alumnos con las relaciones precargadas.

    Precargar ``calificaciones_materia`` (+ su materia), ``calificaciones`` y
    ``grupo_info`` evita el clásico problema N+1: sin esto, serializar el
    listado dispara ~4 consultas por alumno (y una más por cada registro de
    ``CalificacionMateria``), que con la BD remota convierten un listado de
    70 alumnos en ~270 round-trips a la red.
    """
    return (
        Alumno.query
        .options(
            selectinload(Alumno.calificaciones_materia).joinedload(CalificacionMateria.materia),
            selectinload(Alumno.calificaciones),
            selectinload(Alumno.grupo_info),
        )
        .order_by(Alumno.lastname_p.asc(), Alumno.lastname_m.asc(), Alumno.name.asc())
    )


def _serializar_roster(alumnos, califs_por_alumno=None, notas_texto_por_alumno=None):
    """Serializa el roster de alumnos con todas sus notas del catálogo.

    ``califs_por_alumno`` (opcional): ``{alumno_id: nota}`` de la materia en
    curso (roster del docente). En el listado general se omite y la nota de
    la materia en curso queda en ``None``.

    ``notas_texto_por_alumno`` (opcional): ``{alumno_id: nota/comentario}``
    que el docente compartió con el alumno PARA la materia en curso
    (``calificaciones_materia.nota_texto``). Es la única nota de texto que
    se muestra en el panel: la anotación global (``AnotacionAlumno``) quedó
    en desuso y ya no se serializa.
    """
    result = []
    for a in alumnos:
        # Catálogo completo (13 materias): cada nota vía _get_nota_materia
        all_califs = {
            nombre: _get_nota_materia(a, nombre)
            for nombre, _ in MATERIAS_DEFAULT
        }
        # Registros de CalificacionMateria de materias fuera del catálogo
        for cm in a.calificaciones_materia:
            if cm.materia and cm.materia.nombre not in all_califs:
                all_califs[cm.materia.nombre] = (
                    float(cm.calificacion) if cm.calificacion is not None else None
                )

        grupo_text = f"{a.grupo_info.grado}° {a.grupo_info.grupo}" if a.grupo_info else "Sin grupo"

        calif_materia = None
        if califs_por_alumno is not None:
            valor = califs_por_alumno.get(a.id)
            calif_materia = float(valor) if valor is not None else None

        result.append({
            'id': a.id,
            'nombre': a.name,
            'lastname_p': a.lastname_p,
            'lastname_m': a.lastname_m,
            'full_name': a.full_name,
            'group_id': a.group_id,
            'grupo_text': grupo_text,
            'genero': a.genero,
            'status': a.status,
            'codigo': a.password,
            'calificacion_materia': calif_materia,
            'todas_calificaciones': all_califs,
            'nota_texto_materia': (notas_texto_por_alumno or {}).get(a.id, ''),
        })
    return result


@public_bp.route("/")
def home():
    """Página de bienvenida pública con dos opciones: alumno/tutor o profesor."""
    return render_template("public/home.html")


def _crear_alumno_registro(name, lastname_p, lastname_m, group_id, genero):
    """Crea un alumno con código único, guarda y genera su QR."""
    codigo = generar_codigo()
    while Alumno.query.filter_by(password=codigo).first():
        codigo = generar_codigo()

    alumno = Alumno(
        name=name,
        lastname_p=lastname_p,
        lastname_m=lastname_m,
        group_id=group_id,
        genero=genero,
        password=codigo,
        status=True,
    )
    alumno.save()
    alumno.generate_qr_code()
    return alumno


GENEROS_VALIDOS = {'M', 'F', 'Otro'}


def _campos_extra_validos(name, lastname_p, lastname_m, genero):
    """Valida los campos de un bloque adicional antes de crear el alumno.

    Los formularios adicionales no pasan los validadores de WTForms
    (``DataRequired`` / ``Length(max=50)`` del primer form), así que se
    validan aquí con los mismos límites. Evita un ``DataError`` de
    PostgreSQL a mitad del lote (que dejaría alumnos ya commiteados y un
    500) o guardar valores fuera del catálogo de géneros.
    """
    return (
        0 < len(name) <= 50
        and 0 < len(lastname_p) <= 50
        and len(lastname_m) <= 50
        and genero in GENEROS_VALIDOS
    )


@public_bp.route('/alumno/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_alumno():
    form = RegAlumnos()
    if form.validate_on_submit():
        grupo = Grupos.query.get(form.group_id.data)
        grupo_texto = f"{grupo.grado}° {grupo.grupo}" if grupo else 'seleccionado'

        creados = 1
        _crear_alumno_registro(
            name=form.name.data,
            lastname_p=form.lastname_p.data,
            lastname_m=form.lastname_m.data,
            group_id=form.group_id.data,
            genero=form.genero.data,
        )

        # Formularios adicionales (campos indexados name_1, lastname_p_1, …).
        # El grupo se repite del primer formulario: el docente registra todos
        # los alumnos de un mismo grupo. Se saltan bloques vacíos, a medio
        # rellenar o con campos inválidos (el JS puede dejar huecos al quitar
        # bloques).
        for i in range(1, 200):
            name = request.form.get(f'name_{i}', '').strip()
            lastname_p = request.form.get(f'lastname_p_{i}', '').strip()
            lastname_m = request.form.get(f'lastname_m_{i}', '').strip()
            genero = request.form.get(f'genero_{i}', '').strip() or 'M'
            if not _campos_extra_validos(name, lastname_p, lastname_m, genero):
                continue
            _crear_alumno_registro(
                name=name,
                lastname_p=lastname_p,
                lastname_m=lastname_m,
                group_id=form.group_id.data,
                genero=genero,
            )
            creados += 1

        flash(f'{creados} alumno(s) registrado(s) en el grupo {grupo_texto}.', 'success')
        return redirect(url_for('public.docente_panel'))

    return render_template('public/nuevo_alumno.html', form=form)

@public_bp.route("/buscar/")
def buscar_alumno():
    """Página pública de búsqueda con input de código y escáner QR."""
    return render_template("public/alumn_search.html")


@public_bp.route('/buscar/<int:id>')
def boleta_alumno(id):
    """Boleta pública de un alumno por ID (URL directa codificada en el QR).

    El QR de la credencial codifica esta URL absoluta (generada con
    ``url_for(..., _external=True)``); al escanearla con la cámara nativa
    del celular se abre directamente la boleta del alumno.
    """
    alumno = db.session.get(Alumno, id)
    if alumno is None:
        abort(404)
    materias = _materias_boleta(alumno)
    curriculum_activo = _grupo_tiene_curriculum(alumno)
    return render_template(
        "public/calificaciones.html",
        alumno=alumno,
        materias=materias,
        curriculum_activo=curriculum_activo,
    )


@public_bp.route("/calificaciones")
def calificaciones():
    """Boleta pública de calificaciones por código de alumno.

    Recibe el código por query string (``?codigoAlumno=...``), igual que el
    formulario del buscador. Si el código no se envía o no existe ningún
    alumno, la plantilla muestra el estado vacío correspondiente.
    """
    codigo = request.args.get('codigoAlumno')
    alumno = None
    materias = []
    curriculum_activo = False

    if codigo:
        # Resuelve tanto el código de acceso como el ID numérico codificado
        # en los QR (los alumnos creados por rutas públicas codifican el ID).
        alumno = Alumno.find_by_code_or_id(codigo)
        if alumno is not None:
            materias = _materias_boleta(alumno)
            curriculum_activo = _grupo_tiene_curriculum(alumno)

    return render_template(
        "public/calificaciones.html",
        alumno=alumno,
        materias=materias,
        curriculum_activo=curriculum_activo,
    )


@public_bp.route('/qr/<path:filename>')
def servir_qr(filename):
    """Sirve los PNGs de los códigos QR de los alumnos.

    La carpeta se resuelve con la fuente única ``app.utils.qr.qr_codes_folder``:
    si ``QR_CODES_FOLDER`` está definido (p. ej. un disco persistente en
    Render), sirve desde ahí; si no, desde ``<static>/qrcodes``.

    ``filename`` es el valor relativo guardado en ``alumnos.codigo_qr``
    (p. ej. ``qrcodes/alumno_1.png``). Solo se usa el nombre de archivo final,
    nunca la ruta completa (anti path traversal; refuerza la protección de
    ``send_from_directory``).
    """
    from app.utils.qr import qr_codes_folder

    nombre = Path(filename).name
    carpeta = qr_codes_folder()
    if not (carpeta / nombre).is_file():
        abort(404)
    response = send_from_directory(carpeta, nombre)
    # El PNG puede cambiar al regenerarse (mismo nombre, mismo id, p. ej.
    # tras un ``flask regenerate-qrs`` o un cambio de PUBLIC_BASE_URL):
    # ``no-cache`` fuerza la revalidación con el ETag/Last-Modified que ya
    # pone ``send_file`` (304 barato si no cambió) en lugar de arriesgar
    # servir un QR stale desde caché.
    response.headers['Cache-Control'] = 'no-cache'
    return response


@public_bp.route('/api/alumno/register', methods=['POST'])
@login_required
def api_alumno_register():
    """Registra un alumno vía API. Acción exclusiva de administradores."""
    if not es_admin(current_user):
        return jsonify({'error': 'No autorizado: solo el administrador puede registrar alumnos.'}), 403

    data = request.get_json(silent=True) or {}
    required_fields = ['name', 'lastname_p', 'lastname_m', 'group_id', 'genero']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Falta el campo {field}'}), 400

    alumno = _crear_alumno_registro(
        name=data['name'],
        lastname_p=data['lastname_p'],
        lastname_m=data['lastname_m'],
        group_id=data['group_id'],
        genero=data['genero'],
    )

    return jsonify({'alumno': alumno.to_dict(), 'codigo': alumno.password}), 201


@public_bp.route('/api/docente/<int:docente_id>/datos', methods=['GET'])
@login_required
def api_docente_datos(docente_id):
    docente = Docente.get_by_id(docente_id)
    if docente is None:
        return jsonify({'error': 'Docente no encontrado'}), 404

    if current_user.id != docente.id and not current_user.is_admin:
        return jsonify({'error': 'No autorizado'}), 403

    materias = [m.to_dict() for m in docente.materias.order_by(Materia.nombre).all()]
    horarios = [h.to_dict() for h in _horarios_de_docente(docente.id)]

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
        # El cambio de estatus es exclusivo del administrador
        if es_admin(current_user):
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
        return redirect(url_for('public.docente_panel'))

    return render_template('public/edit_alumno.html', alumno=alumno, form=form)


@public_bp.route('/alumno/<int:alumno_id>/baja', methods=['POST'])
@login_required
def baja_alumno(alumno_id):
    """Da de baja a un alumno (formulario). Acción exclusiva de administradores."""
    if not es_admin(current_user):
        abort(401)
    alumno = Alumno.query.get_or_404(alumno_id)
    alumno.status = False
    alumno.save()
    return redirect(url_for('public.docente_panel'))


@public_bp.route("/docente/")
@login_required
def docente_panel():
    """
    Panel del docente autenticado.
    Muestra sus materias asignadas y su horario semanal.
    """
    docente = current_user
    materias = docente.materias.order_by(Materia.nombre).all()
    horarios = _horarios_de_docente(docente.id)
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

    horarios = _horarios_de_docente(docente_id)

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


@public_bp.route("/api/grupos", methods=['GET'])
@login_required
def api_get_grupos():
    from app.models import Grupos
    grupos = Grupos.query.all()
    return jsonify([
        {'id': g.id, 'grado': g.grado, 'grupo': g.grupo, 'nombre': f"{g.grado}° {g.grupo}"}
        for g in grupos
    ])


@public_bp.route("/api/materia/<int:materia_id>/alumnos", methods=['GET'])
@login_required
def api_materia_alumnos(materia_id):
    """Listado de alumnos con sus calificaciones para una materia.

    El admin puede consultar cualquier materia; un docente solo las que imparte.
    El roster solo incluye alumnos de grupos cuyo currículum tenga la materia
    asignada (si ningún grupo la tiene configurada, se muestran todos).
    """
    materia = Materia.query.get_or_404(materia_id)

    if not es_admin(current_user) and not _docente_imparte_materia(current_user, materia.nombre):
        return jsonify({'error': 'No autorizado: no impartes la materia indicada.'}), 403

    is_admin = es_admin(current_user)
    grupos_ids = None
    filtrado_por_docente = False
    query = _alumnos_ordenados_con_cargas()

    if not is_admin:
        # ── Filtro por docente: solo alumnos de los grupos donde imparte
        #    la materia según su horario (horarios.grupo_id). Estricto: sin
        #    horario asignado para esta materia no ve alumnos. ──
        grupos_docente = _grupos_docente_para_materia(current_user.id, materia.id)
        filtrado_por_docente = True
        if not grupos_docente:
            return jsonify({
                'materia': materia.to_dict(),
                'is_admin_user': False,
                'curriculum_filtrado': False,
                'filtrado_por_docente': True,
                'alumnos': [],
            })
        query = query.filter(Alumno.group_id.in_(grupos_docente))
    else:
        # ── Filtro por currículum (admin): solo alumnos de grupos donde se
        #    imparte la materia; si ningún grupo la tiene, todos. ──
        grupos_ids = _grupos_con_materia(materia)
        if grupos_ids:
            query = query.filter(Alumno.group_id.in_(grupos_ids))

    alumnos = query.all()

    # Nota de la materia en curso (numérica y el comentario del docente).
    # Ambas se leen de las relaciones ya precargadas en
    # ``_alumnos_ordenados_con_cargas`` (sin consultas extra por fila).
    califs_por_alumno = {a.id: _get_nota_materia(a, materia.nombre) for a in alumnos}
    notas_texto_por_alumno = {a.id: _get_nota_texto_materia(a, materia.nombre) for a in alumnos}
    result = _serializar_roster(alumnos, califs_por_alumno, notas_texto_por_alumno)

    return jsonify({
        'materia': materia.to_dict(),
        'is_admin_user': is_admin,
        'curriculum_filtrado': bool(grupos_ids),
        'filtrado_por_docente': filtrado_por_docente,
        'alumnos': result
    })


@public_bp.route("/api/admin/alumnos", methods=['GET'])
@login_required
def api_admin_alumnos():
    is_admin = es_admin(current_user)
    if not is_admin:
        return jsonify({'error': 'No autorizado'}), 403

    alumnos = _alumnos_ordenados_con_cargas().all()
    # Sin materia en curso: el listado general solo serializa las notas
    # numéricas de todas las materias (sin nota de texto de una materia
    # concreta, porque no hay una materia seleccionada).
    result = _serializar_roster(alumnos)

    return jsonify({
        'materia': None,
        'is_admin_user': True,
        'alumnos': result
    })


@public_bp.route("/api/alumno/<int:alumno_id>/baja_logica", methods=['POST'])
@login_required
def api_alumno_baja_logica(alumno_id):
    """Da de baja lógica a un alumno. Acción exclusiva de administradores."""
    if not es_admin(current_user):
        return jsonify({'error': 'No autorizado: solo el administrador puede dar de baja.'}), 403
    alumno = Alumno.query.get_or_404(alumno_id)
    alumno.status = False
    alumno.save()
    return jsonify({'success': True, 'message': f'Alumno {alumno.full_name} dado de baja.'})


@public_bp.route("/api/alumno/<int:alumno_id>/update_docente", methods=['POST'])
@login_required
def api_alumno_update_docente(alumno_id):
    try:
        ensure_required_tables()
        alumno = Alumno.query.get_or_404(alumno_id)
        data = request.get_json(silent=True) or {}
        is_admin = es_admin(current_user)

        # ── Autorización (anti-IDOR) ──────────────────────────────
        if not is_admin:
            # El docente NO puede cambiar el estatus ni editar todas las materias
            if 'status' in data:
                return jsonify({'error': 'Solo el administrador puede cambiar el estatus.'}), 403
            if 'todas_calificaciones' in data:
                return jsonify({'error': 'Solo el administrador puede editar todas las calificaciones.'}), 403
            # Solo puede calificar materias que imparte
            if data.get('materia_nombre') and not _docente_imparte_materia(current_user, data['materia_nombre']):
                return jsonify({'error': 'No autorizado: no impartes la materia indicada.'}), 403

        # ── Datos de identidad (permitidos a admin y docentes) ────
        if 'name' in data and data['name']:
            alumno.name = data['name']
        if 'lastname_p' in data and data['lastname_p']:
            alumno.lastname_p = data['lastname_p']
        if 'lastname_m' in data:
            alumno.lastname_m = data['lastname_m']
        if 'group_id' in data and data['group_id']:
            alumno.group_id = int(data['group_id'])
        if 'genero' in data and data['genero']:
            alumno.genero = data['genero']
        if is_admin and 'status' in data:
            alumno.status = bool(data['status'])
        if 'codigo' in data and data['codigo']:
            alumno.password = data['codigo']

        alumno.save()

        # ── Calificaciones: columna fija (mapa) o CalificacionMateria ──
        if is_admin and 'todas_calificaciones' in data and isinstance(data['todas_calificaciones'], dict):
            for m_nombre, m_valor in data['todas_calificaciones'].items():
                _set_nota_materia(alumno, m_nombre, m_valor)
        elif 'materia_nombre' in data and 'calificacion' in data:
            _set_nota_materia(alumno, data['materia_nombre'], data['calificacion'])

        # Nota/comentario del docente PARA la materia en curso (vacío = borrar).
        # Es la nota por materia de ``calificaciones_materia.nota_texto``: la
        # misma que se ve en la boleta y en la vista de edición. La anotación
        # global antigua (AnotacionAlumno) quedó en desuso.
        if 'materia_nombre' in data and 'nota_texto' in data:
            _set_nota_texto_materia(alumno, data['materia_nombre'], data['nota_texto'])

        db.session.commit()
        # Devolver la nota por materia ya normalizada (strip + vacío→None)
        # para que el frontend refleje exactamente lo persistido.
        nota_texto_materia = ''
        if data.get('materia_nombre'):
            nota_texto_materia = _get_nota_texto_materia(alumno, data['materia_nombre'])
        return jsonify({
            'success': True,
            'alumno': alumno.to_dict(),
            'nota_texto_materia': nota_texto_materia,
        })
    except Exception as exc:
        logger.exception('Error guardando la calificación del alumno %s', alumno_id)
        return jsonify({'success': False, 'error': str(exc)}), 500


@public_bp.route('/docente/alumno/<int:alumno_id>/editar', methods=['GET', 'POST'])
@login_required
def docente_editar_alumno(alumno_id):
    """Vista de edición del alumno para el docente.

    Estéticamente idéntica a la boleta que ve el alumno/tutor tras una
    búsqueda exitosa (``public/calificaciones.html``), pero con los campos
    de información del alumno editables (``<input>``/``<select>``), la
    calificación de una materia (la del roster o cualquiera que el docente
    imparta) y un botón de guardado vía POST seguro (CSRF).
    """
    alumno = Alumno.query.get_or_404(alumno_id)

    # ── Autorización anti-IDOR ───────────────────────────────────────
    # Solo el admin o un docente que imparta una materia del alumno (del
    # currículum de su grupo) puede ver/editar sus datos o descargar su QR.
    if not es_admin(current_user) and not _docente_imparte_materias_del_alumno(current_user, alumno):
        abort(401)

    # ── Materias disponibles para calificar (anti-IDOR) ──────────────
    # El admin puede calificar cualquier materia; el docente solo las que
    # imparte y que además están en el currículum del grupo del alumno
    # (si el grupo tiene currículum configurado). Sin este cruce, un
    # docente que imparte varias materias podría calificar al alumno en
    # una materia que su grupo no cursa — incoherente con la boleta, que
    # solo muestra el currículum del grupo.
    is_admin = es_admin(current_user)
    if is_admin:
        materias_disponibles = Materia.query.order_by(Materia.nombre).all()
    else:
        materias_docente = {m.id for m in current_user.materias.all()}
        materias = Materia.query.order_by(Materia.nombre).all()
        grupo = alumno.grupo_info
        if grupo is not None and grupo.materias.first() is not None:
            # Currículum del grupo: intersección con las materias del docente.
            curric_ids = {m.id for m in grupo.materias.all()}
            materias_disponibles = [
                m for m in materias
                if m.id in materias_docente and m.id in curric_ids
            ]
        else:
            # Sin currículum: la boleta muestra el catálogo completo, así que
            # basta con que el docente imparta la materia.
            materias_disponibles = [m for m in materias if m.id in materias_docente]

    # Materia preseleccionada: viene del roster (query string ?materia_id=)
    # o, si no, la primera disponible.
    #
    # Cuando se entra desde el roster de una materia (?materia_id= válido),
    # el select de materia queda BLOQUEADO: el docente solo califica la
    # materia desde la que vino, no puede cambiarla. Si el id no está entre
    # las materias disponibles (anti-IDOR), no se bloquea y cae a la primera.
    materia_id_orig = request.args.get('materia_id', type=int)
    materia_ids = [m.id for m in materias_disponibles]
    materia_bloqueada = materia_id_orig in materia_ids
    materia_id_qs = materia_id_orig
    if materia_id_qs not in materia_ids:
        materia_id_qs = materia_ids[0] if materia_ids else None

    form = DocenteEditAlumnoForm(
        tutor_actual_id=alumno.tutor_id,
        materias_choices=[(str(m.id), m.nombre) for m in materias_disponibles],
    )

    if request.method == 'GET':
        form.name.data = alumno.name
        form.lastname_p.data = alumno.lastname_p
        form.lastname_m.data = alumno.lastname_m
        form.genero.data = alumno.genero
        form.group_id.data = alumno.group_id
        form.password.data = alumno.password
        form.tutor_id.data = alumno.tutor_id or 0
        form.materia_id.data = materia_id_qs
        # Cargar la calificación y la nota/comentario actuales de la materia
        # preseleccionada
        materia_sel = next((m for m in materias_disponibles if m.id == materia_id_qs), None)
        if materia_sel is not None:
            form.calificacion.data = _get_nota_materia(alumno, materia_sel.nombre)
            form.nota_texto.data = _get_nota_texto_materia(alumno, materia_sel.nombre)

    if form.validate_on_submit():
        # Mismo conjunto de campos de identidad que permite editar
        # ``api_alumno_update_docente`` (el estatus es exclusivo del admin).
        alumno.name = form.name.data
        alumno.lastname_p = form.lastname_p.data
        alumno.lastname_m = form.lastname_m.data
        alumno.genero = form.genero.data
        alumno.group_id = form.group_id.data
        # Normalizar a mayúsculas: los códigos generados son mayúsculas y la
        # búsqueda por código es sensible a mayúsculas.
        alumno.password = (form.password.data or '').strip().upper()
        # Profesor asignado: 0 (o vacío) significa "sin asignar".
        alumno.tutor_id = form.tutor_id.data or None

        # ── Calificación y nota/comentario (si se eligió materia) ──────
        if form.materia_id.data:
            materia_sel = next(
                (m for m in materias_disponibles if m.id == form.materia_id.data),
                None,
            )
            if materia_sel is not None:
                # La nota numérica se guarda solo si se envió un valor
                if form.calificacion.data is not None:
                    _set_nota_materia(alumno, materia_sel.nombre, form.calificacion.data)
                # La nota/comentario se guarda siempre (vacío = borrar)
                _set_nota_texto_materia(alumno, materia_sel.nombre, form.nota_texto.data)

        # ``save()`` ya hace commit (incluye los cambios de _set_nota_materia
        # añadidos a la sesión antes).
        alumno.save()
        flash(f'Datos del alumno {alumno.full_name} actualizados.', 'success')
        return redirect(url_for('public.docente_panel'))

    # Docentes que imparten cada materia al grupo del alumno (horario).
    # Se muestran bajo el select de materia para que el docente sepa quién
    # imparte la materia que va a calificar (misma fuente que la boleta).
    docentes_por_materia = _docentes_por_materia_grupo(alumno)

    return render_template(
        'public/editar_alumno_docente.html',
        alumno=alumno,
        form=form,
        materias_disponibles=materias_disponibles,
        materia_id_qs=materia_id_qs,
        materia_bloqueada=materia_bloqueada,
        docentes_por_materia=docentes_por_materia,
    )


@public_bp.route('/docente/alumno/<int:alumno_id>/qr-pdf')
@login_required
def docente_alumno_qr_pdf(alumno_id):
    """Descarga el PDF de credencial QR del alumno.

    Genera dinámicamente un PDF simple con el código QR del alumno y su
    nombre (Nombre + Primer Apellido) y lo devuelve como descarga directa.
    """
    alumno = Alumno.query.get_or_404(alumno_id)

    # ── Autorización anti-IDOR (misma regla que la vista de edición) ──
    if not es_admin(current_user) and not _docente_imparte_materias_del_alumno(current_user, alumno):
        abort(401)

    pdf_buf = generar_pdf_qr(alumno)

    return send_file(
        pdf_buf,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'qr_alumno_{alumno.id}.pdf',
    )


@public_bp.route('/docente/alumno/<int:alumno_id>/qr-imagen')
@login_required
def docente_alumno_qr_imagen(alumno_id):
    """Descarga la credencial QR del alumno como imagen PNG.

    Mismo contenido y layout que el PDF (``generar_pdf_qr``): el código QR
    del alumno y su nombre (Nombre + Primer Apellido), generados al vuelo
    en proporción carta. La autorización anti-IDOR es idéntica a la del
    PDF y a la de la vista de edición.
    """
    alumno = Alumno.query.get_or_404(alumno_id)

    if not es_admin(current_user) and not _docente_imparte_materias_del_alumno(current_user, alumno):
        abort(401)

    img_buf = generar_imagen_qr(alumno)

    return send_file(
        img_buf,
        mimetype='image/png',
        as_attachment=True,
        download_name=f'qr_alumno_{alumno.id}.png',
    )

