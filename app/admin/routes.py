import datetime

from flask import render_template, redirect, url_for, abort, flash, request
from flask_login import current_user, login_required
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app import db
from app.auth.decorators import admin_required
from app.auth.models import Docente, ROL_ADMIN_ID
from app.models import Alumno, Grupos, Horario, Materia, grupos_materias
from app.utils.codes import generar_codigo
from . import admin_bp
from .forms import (AlumnoAdminForm, DocenteAdminForm, GrupoForm,
                    GrupoMateriasForm, HorarioAdminForm)


@admin_bp.route("/admin/")
@login_required
@admin_required
def index():
    """Panel de administración principal."""
    total_docentes = Docente.query.count()
    docentes_activos = Docente.query.filter_by(estatus=True).count()
    total_grupos = Grupos.query.count()
    total_alumnos = Alumno.query.count()
    return render_template("admin/index.html",
                           total_docentes=total_docentes,
                           docentes_activos=docentes_activos,
                           total_grupos=total_grupos,
                           total_alumnos=total_alumnos)


# ──────────────────────────────────────────────
#  ALUMNOS (CRUD en admin)
# ──────────────────────────────────────────────

@admin_bp.route("/admin/alumnos/")
@login_required
@admin_required
def list_alumnos():
    """Lista todos los alumnos con filtro."""
    # selectinload(grupo_info): la plantilla accede a alumno.grupo_info por
    # fila; sin precargarlo se dispara 1 query por alumno (N+1)
    alumnos = Alumno.query\
        .options(selectinload(Alumno.grupo_info))\
        .order_by(Alumno.id.asc()).all()
    return render_template("admin/alumnos.html", alumnos=alumnos)


@admin_bp.route("/admin/alumnos/nuevo/", methods=['GET', 'POST'])
@login_required
@admin_required
def create_alumno():
    """Registra un nuevo alumno con código manual o automático + QR."""
    form = AlumnoAdminForm()
    if form.validate_on_submit():
        # Determinar código
        if form.auto_generar_codigo.data:
            codigo = generar_codigo()
            while Alumno.query.filter_by(password=codigo).first():
                codigo = generar_codigo()
        else:
            codigo = form.codigo_manual.data
            if not codigo:
                flash('Debes ingresar un código manual o activar la generación automática.', 'error')
                return render_template("admin/alumno_form.html", form=form)
            if Alumno.query.filter_by(password=codigo).first():
                flash(f'El código "{codigo}" ya está en uso por otro alumno.', 'error')
                return render_template("admin/alumno_form.html", form=form)

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

        # Generar QR (codifica la URL absoluta de la boleta del alumno)
        alumno.generate_qr_code()

        flash(f'Alumno {alumno.name} registrado con código {codigo}.', 'success')
        return redirect(url_for('admin.list_alumnos'))

    return render_template("admin/alumno_form.html", form=form)


@admin_bp.route("/admin/alumnos/<int:alumno_id>/editar/", methods=['GET', 'POST'])
@login_required
@admin_required
def edit_alumno(alumno_id):
    """Edita los datos de un alumno."""
    alumno = Alumno.query.get_or_404(alumno_id)
    form = AlumnoAdminForm()

    if request.method == 'GET':
        form.name.data = alumno.name
        form.lastname_p.data = alumno.lastname_p
        form.lastname_m.data = alumno.lastname_m
        form.genero.data = alumno.genero
        form.group_id.data = alumno.group_id
        form.codigo_manual.data = alumno.password
        form.auto_generar_codigo.data = False

    if form.validate_on_submit():
        alumno.name = form.name.data
        alumno.lastname_p = form.lastname_p.data
        alumno.lastname_m = form.lastname_m.data
        alumno.genero = form.genero.data
        alumno.group_id = form.group_id.data

        # Actualizar código solo si el admin ingresa uno nuevo
        if form.codigo_manual.data and form.codigo_manual.data != alumno.password:
            if Alumno.query.filter_by(password=form.codigo_manual.data).first():
                flash(f'El código "{form.codigo_manual.data}" ya está en uso.', 'error')
                return render_template("admin/alumno_form.html", form=form, alumno=alumno)
            alumno.password = form.codigo_manual.data

        alumno.save()
        flash(f'Alumno {alumno.name} actualizado.', 'success')
        return redirect(url_for('admin.list_alumnos'))

    return render_template("admin/alumno_form.html", form=form, alumno=alumno)


@admin_bp.route("/admin/alumnos/<int:alumno_id>/baja/", methods=['POST'])
@login_required
@admin_required
def baja_alumno(alumno_id):
    """Da de baja lógica a un alumno (cambia status a False)."""
    alumno = Alumno.query.get_or_404(alumno_id)
    alumno.status = not alumno.status
    alumno.save()
    estado = 'dado de alta' if alumno.status else 'dado de baja'
    flash(f'Alumno {alumno.name} {estado}.', 'success')
    return redirect(url_for('admin.list_alumnos'))


# ──────────────────────────────────────────────
#  DOCENTES (CRUD)
# ──────────────────────────────────────────────

@admin_bp.route("/admin/docentes/")
@login_required
@admin_required
def list_docentes():
    """Lista todos los docentes registrados."""
    docentes = Docente.get_all()
    return render_template("admin/docentes.html", docentes=docentes)


@admin_bp.route("/admin/docentes/nuevo/", methods=['GET', 'POST'])
@login_required
@admin_required
def create_docente():
    """Crea un nuevo docente con asignación de materias."""
    form = DocenteAdminForm()
    if form.validate_on_submit():
        docente = Docente.get_by_email(form.email.data)
        if docente is not None:
            flash(f'El email {form.email.data} ya está en uso.', 'error')
            return render_template("admin/docente_form.html", form=form)

        docente = Docente(
            name=form.name.data,
            apellidos=form.apellidos.data,
            email=form.email.data,
            rol=form.rol.data
        )
        docente.set_password(form.password.data)

        # Asignar materias seleccionadas
        if form.materias.data:
            materias = Materia.query.filter(Materia.id.in_(form.materias.data)).all()
            docente.materias = materias

        docente.save()
        flash(f'Docente {docente.nombre} creado exitosamente con {len(form.materias.data)} materia(s).', 'success')
        return redirect(url_for('admin.list_docentes'))

    return render_template("admin/docente_form.html", form=form)


@admin_bp.route("/admin/docentes/<int:docente_id>/", methods=['GET', 'POST'])
@login_required
@admin_required
def edit_docente(docente_id):
    """Edita un docente existente (incluyendo materias asignadas)."""
    docente = Docente.get_by_id(docente_id)
    if docente is None:
        abort(404)

    form = DocenteAdminForm()

    if request.method == 'GET':
        form.name.data = docente.nombre
        form.apellidos.data = docente.apellidos
        form.email.data = docente.email
        form.rol.data = docente.rol
        form.materias.data = [m.id for m in docente.materias.all()]

    if form.validate_on_submit():
        # No permitir que el admin se quite el rol a sí mismo
        if docente.id == current_user.id and form.rol.data != ROL_ADMIN_ID:
            flash('No puedes cambiarte el rol a ti mismo.', 'error')
            return render_template("admin/docente_form.html", form=form, docente=docente)

        docente.nombre = form.name.data
        docente.apellidos = form.apellidos.data
        docente.email = form.email.data
        docente.rol = form.rol.data

        if form.password.data:
            docente.set_password(form.password.data)

        # Actualizar materias asignadas
        materias_seleccionadas = Materia.query.filter(
            Materia.id.in_(form.materias.data)
        ).all() if form.materias.data else []
        docente.materias = materias_seleccionadas

        docente.save()
        flash(f'Docente {docente.nombre} actualizado.', 'success')
        return redirect(url_for('admin.list_docentes'))

    return render_template("admin/docente_form.html", form=form, docente=docente)


@admin_bp.route("/admin/docentes/<int:docente_id>/toggle/", methods=['POST'])
@login_required
@admin_required
def toggle_docente(docente_id):
    """Activa/desactiva un docente."""
    docente = Docente.get_by_id(docente_id)
    if docente is None:
        abort(404)

    if docente.id == current_user.id:
        flash('No puedes desactivarte a ti mismo.', 'error')
        return redirect(url_for('admin.list_docentes'))

    docente.estatus = not docente.estatus
    docente.save()
    estado = 'activado' if docente.estatus else 'desactivado'
    flash(f'Docente {docente.nombre} {estado}.', 'success')
    return redirect(url_for('admin.list_docentes'))


@admin_bp.route("/admin/docentes/<int:docente_id>/delete/", methods=['POST'])
@login_required
@admin_required
def delete_docente(docente_id):
    """Elimina un docente."""
    docente = Docente.get_by_id(docente_id)
    if docente is None:
        abort(404)

    if docente.id == current_user.id:
        flash('No puedes eliminarte a ti mismo.', 'error')
        return redirect(url_for('admin.list_docentes'))

    docente.delete()
    flash(f'Docente {docente.nombre} eliminado.', 'success')
    return redirect(url_for('admin.list_docentes'))


# ──────────────────────────────────────────────
#  GRUPOS (CRUD)
# ──────────────────────────────────────────────

@admin_bp.route("/admin/grupos/")
@login_required
@admin_required
def list_grupos():
    """Lista todos los grupos registrados."""
    # selectinload(alumnos): la plantilla usa grupo.alumnos por fila (N+1)
    grupos = Grupos.query\
        .options(selectinload(Grupos.alumnos))\
        .order_by(Grupos.grado, Grupos.grupo).all()

    # Conteo de materias del currículum por grupo en una sola consulta
    # (antes: grupo.materias.count() por fila = 1 query por grupo)
    filas = db.session.execute(
        select(grupos_materias.c.grupo_id, func.count(grupos_materias.c.materia_id))
        .group_by(grupos_materias.c.grupo_id)
    ).all()
    materias_por_grupo = {g_id: total for g_id, total in filas}

    return render_template("admin/grupos.html", grupos=grupos, materias_por_grupo=materias_por_grupo)


@admin_bp.route("/admin/grupos/nuevo/", methods=['GET', 'POST'])
@login_required
@admin_required
def create_grupo():
    """Crea un nuevo grupo."""
    form = GrupoForm()
    if form.validate_on_submit():
        # Verificar que no exista ya
        existente = Grupos.query.filter_by(
            grado=form.grado.data,
            grupo=form.grupo.data
        ).first()
        if existente:
            flash(f'El grupo {form.grado.data}° {form.grupo.data} ya existe.', 'error')
            return render_template("admin/grupo_form.html", form=form)

        grupo = Grupos(grado=form.grado.data, grupo=form.grupo.data)
        grupo.save()
        flash(f'Grupo {grupo.grado}° {grupo.grupo} creado exitosamente.', 'success')
        return redirect(url_for('admin.list_grupos'))

    return render_template("admin/grupo_form.html", form=form)


@admin_bp.route("/admin/grupos/<int:grupo_id>/", methods=['GET', 'POST'])
@login_required
@admin_required
def edit_grupo(grupo_id):
    """Edita un grupo existente."""
    grupo = Grupos.query.get_or_404(grupo_id)
    form = GrupoForm()

    if request.method == 'GET':
        form.grado.data = grupo.grado
        form.grupo.data = grupo.grupo

    if form.validate_on_submit():
        # Verificar que no haya duplicado (excepto el mismo)
        existente = Grupos.query.filter_by(
            grado=form.grado.data,
            grupo=form.grupo.data
        ).first()
        if existente and existente.id != grupo.id:
            flash(f'El grupo {form.grado.data}° {form.grupo.data} ya existe.', 'error')
            return render_template("admin/grupo_form.html", form=form, grupo=grupo)

        grupo.grado = form.grado.data
        grupo.grupo = form.grupo.data
        grupo.save()
        flash(f'Grupo {grupo.grado}° {grupo.grupo} actualizado.', 'success')
        return redirect(url_for('admin.list_grupos'))

    return render_template("admin/grupo_form.html", form=form, grupo=grupo)


@admin_bp.route("/admin/grupos/<int:grupo_id>/delete/", methods=['POST'])
@login_required
@admin_required
def delete_grupo(grupo_id):
    """Elimina un grupo (solo si no tiene alumnos asignados)."""
    grupo = Grupos.query.get_or_404(grupo_id)

    if grupo.alumnos:
        flash(f'No se puede eliminar el grupo {grupo.grado}° {grupo.grupo} porque tiene {len(grupo.alumnos)} alumno(s) asignado(s).', 'error')
        return redirect(url_for('admin.list_grupos'))

    grupo.delete()
    flash(f'Grupo {grupo.grado}° {grupo.grupo} eliminado.', 'success')
    return redirect(url_for('admin.list_grupos'))


@admin_bp.route("/admin/grupos/<int:grupo_id>/materias/", methods=['GET', 'POST'])
@login_required
@admin_required
def edit_grupo_materias(grupo_id):
    """Asigna el currículum del grupo: las materias que se imparten en él.

    La boleta de cada alumno del grupo mostrará únicamente estas materias.
    """
    grupo = Grupos.query.get_or_404(grupo_id)
    form = GrupoMateriasForm()

    if request.method == 'GET':
        form.materias.data = [m.id for m in grupo.materias.all()]

    if form.validate_on_submit():
        materias_seleccionadas = Materia.query.filter(
            Materia.id.in_(form.materias.data)
        ).all() if form.materias.data else []
        grupo.materias = materias_seleccionadas
        grupo.save()
        flash(f'Materias del grupo {grupo.grado}° {grupo.grupo} actualizadas.', 'success')
        return redirect(url_for('admin.list_grupos'))

    return render_template("admin/grupo_materias.html", form=form, grupo=grupo)


# ──────────────────────────────────────────────
#  HORARIOS (CRUD) — asignación docente ↔ grupo
# ──────────────────────────────────────────────

def _parse_hora(texto):
    """Parsea una hora a ``datetime.time`` o lanza ValueError.

    Acepta tanto ``HH:MM`` como ``HH:MM:SS``: el input ``type="time"``
    del formulario envía ``HH:MM`` por defecto, pero con ciertos ``step``
    o navegadores puede llegar con segundos.
    """
    texto = (texto or '').strip()
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.datetime.strptime(texto, fmt).time()
        except ValueError:
            continue
    raise ValueError(f'Hora no válida: {texto}')


def _horario_solapado(docente_id, dia_semana, hora_inicio, hora_fin, excluir_id=None):
    """¿El docente ya tiene una clase que se solape con el rango horario?

    Dos bloques se solapan si sus intervalos se cruzan: ``a < fin_b`` y
    ``b < fin_a``. Al editar se excluye el propio horario (``excluir_id``)
    para que un docente pueda conservar su clase sin bloquearse a sí mismo.
    """
    query = Horario.query.filter(
        Horario.docente_id == docente_id,
        Horario.dia_semana == dia_semana,
        Horario.hora_inicio < hora_fin,
        Horario.hora_fin > hora_inicio,
    )
    if excluir_id is not None:
        query = query.filter(Horario.id != excluir_id)
    return query.first() is not None


@admin_bp.route("/admin/horarios/")
@login_required
@admin_required
def list_horarios():
    """Lista las entradas del horario con docente, materia y grupo precargados."""
    horarios = Horario.query\
        .options(
            selectinload(Horario.docente),
            selectinload(Horario.materia),
            selectinload(Horario.grupo),
        )\
        .order_by(Horario.dia_semana, Horario.hora_inicio)\
        .all()
    return render_template("admin/horarios.html", horarios=horarios)


@admin_bp.route("/admin/horarios/nuevo/", methods=['GET', 'POST'])
@login_required
@admin_required
def create_horario():
    """Crea una entrada de horario (docente + materia + grupo + día/hora)."""
    form = HorarioAdminForm()
    if form.validate_on_submit():
        try:
            hora_inicio = _parse_hora(form.hora_inicio.data)
            hora_fin = _parse_hora(form.hora_fin.data)
        except ValueError:
            flash('Formato de hora inválido. Usa HH:MM (ej. 07:30).', 'error')
            return render_template("admin/horario_form.html", form=form)
        if hora_fin <= hora_inicio:
            flash('La hora de fin debe ser posterior a la de inicio.', 'error')
            return render_template("admin/horario_form.html", form=form)

        # Anti-solapamiento: un docente no puede tener dos clases a la vez
        # (mismo día y rango horario cruzado).
        if _horario_solapado(
            form.docente_id.data, form.dia_semana.data,
            hora_inicio, hora_fin,
        ):
            flash('El docente ya tiene una clase en ese día y horario (se superponen).', 'error')
            return render_template("admin/horario_form.html", form=form)

        horario = Horario(
            docente_id=form.docente_id.data,
            materia_id=form.materia_id.data,
            grupo_id=form.grupo_id.data or None,  # 0 → sin grupo
            dia_semana=form.dia_semana.data,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            salon=form.salon.data or None,
        )
        horario.save()
        flash('Entrada de horario creada.', 'success')
        return redirect(url_for('admin.list_horarios'))

    return render_template("admin/horario_form.html", form=form)


@admin_bp.route("/admin/horarios/<int:horario_id>/editar/", methods=['GET', 'POST'])
@login_required
@admin_required
def edit_horario(horario_id):
    """Edita una entrada de horario existente."""
    horario = db.session.get(Horario, horario_id)
    if horario is None:
        abort(404)

    form = HorarioAdminForm()

    if request.method == 'GET':
        form.docente_id.data = horario.docente_id
        form.materia_id.data = horario.materia_id
        form.grupo_id.data = horario.grupo_id or 0
        form.dia_semana.data = horario.dia_semana
        form.hora_inicio.data = horario.hora_inicio.strftime('%H:%M')
        form.hora_fin.data = horario.hora_fin.strftime('%H:%M')
        form.salon.data = horario.salon

    if form.validate_on_submit():
        try:
            hora_inicio = _parse_hora(form.hora_inicio.data)
            hora_fin = _parse_hora(form.hora_fin.data)
        except ValueError:
            flash('Formato de hora inválido. Usa HH:MM (ej. 07:30).', 'error')
            return render_template("admin/horario_form.html", form=form, horario=horario)
        if hora_fin <= hora_inicio:
            flash('La hora de fin debe ser posterior a la de inicio.', 'error')
            return render_template("admin/horario_form.html", form=form, horario=horario)

        # Anti-solapamiento (excluyendo el propio horario): el docente no
        # puede tener otra clase a la vez en el mismo día.
        if _horario_solapado(
            form.docente_id.data, form.dia_semana.data,
            hora_inicio, hora_fin, excluir_id=horario.id,
        ):
            flash('El docente ya tiene una clase en ese día y horario (se superponen).', 'error')
            return render_template("admin/horario_form.html", form=form, horario=horario)

        horario.docente_id = form.docente_id.data
        horario.materia_id = form.materia_id.data
        horario.grupo_id = form.grupo_id.data or None
        horario.dia_semana = form.dia_semana.data
        horario.hora_inicio = hora_inicio
        horario.hora_fin = hora_fin
        horario.salon = form.salon.data or None
        horario.save()
        flash('Entrada de horario actualizada.', 'success')
        return redirect(url_for('admin.list_horarios'))

    return render_template("admin/horario_form.html", form=form, horario=horario)


@admin_bp.route("/admin/horarios/<int:horario_id>/eliminar/", methods=['POST'])
@login_required
@admin_required
def delete_horario(horario_id):
    """Elimina una entrada de horario."""
    horario = db.session.get(Horario, horario_id)
    if horario is None:
        abort(404)
    horario.delete()
    flash('Entrada de horario eliminada.', 'success')
    return redirect(url_for('admin.list_horarios'))
