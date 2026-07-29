import logging
import secrets
import string as string_module
from pathlib import Path

import qrcode
from flask import render_template, redirect, url_for, abort, flash, request, current_app
from flask_login import current_user, login_required
from app.auth.decorators import admin_required
from app.auth.models import Docente
from app.models import Alumno, Grupos, Materia
from . import admin_bp
from .forms import AlumnoAdminForm, DocenteAdminForm, GrupoForm

logger = logging.getLogger(__name__)


def _generar_codigo(longitud=10):
    """Genera un código alfanumérico aleatorio de 10 caracteres."""
    alfabeto = string_module.ascii_uppercase + string_module.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(longitud))


def _generar_qr(codigo, alumno_id):
    """Genera un código QR para el alumno y guarda la ruta."""
    qr_folder = Path(current_app.static_folder) / 'qrcodes'
    qr_folder.mkdir(parents=True, exist_ok=True)
    qr_filename = f'alumno_{alumno_id}.png'
    qr_path = qr_folder / qr_filename
    qr_image = qrcode.make(codigo)
    qr_image.save(qr_path)
    return f'qrcodes/{qr_filename}'


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
    alumnos = Alumno.query.order_by(Alumno.id.asc()).all()
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
            codigo = _generar_codigo()
            while Alumno.query.filter_by(password=codigo).first():
                codigo = _generar_codigo()
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

        # Generar QR
        alumno.generate_qr_code(codigo)

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
        if docente.id == current_user.id and form.rol.data != 'admin':
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
    grupos = Grupos.query.order_by(Grupos.grado, Grupos.grupo).all()
    return render_template("admin/grupos.html", grupos=grupos)


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
