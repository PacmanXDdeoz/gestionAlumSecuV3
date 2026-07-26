import logging
import os
from pathlib import Path

import qrcode
from flask import abort, render_template, redirect, url_for, request, current_app
from flask_login import current_user, login_required

# from app.models import Post, Comment
from app.models import Alumno, Calificacion
from . import public_bp
from .forms import AlumnoEditForm, RegAlumnos
# from .forms import CommentForm

logger = logging.getLogger(__name__)


@public_bp.route("/")
@login_required
def index():
    alumnos = Alumno.query.order_by(Alumno.id.asc()).all()
    return render_template("public/index.html", alumno=alumnos)


@public_bp.route('/alumno/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_alumno():
    form = RegAlumnos()
    if form.validate_on_submit():
        alumno = Alumno(
            name=form.name.data,
            lastname_p=form.lastname_p.data,
            lastname_m=form.lastname_m.data,
            group_id=form.group_id.data,
            genero=form.genero.data,
            password=form.password.data,
            status=form.status.data if hasattr(form, 'status') else True,
        )
        alumno.save()

        qr_folder = Path(current_app.static_folder) / 'qrcodes'
        qr_folder.mkdir(parents=True, exist_ok=True)
        qr_filename = f'alumno_{alumno.id}.png'
        qr_path = qr_folder / qr_filename
        qr_image = qrcode.make(str(alumno.id))
        qr_image.save(qr_path)
        alumno.codigo_qr = f'qrcodes/{qr_filename}'
        alumno.save()

        return redirect(url_for('public.index'))

    return render_template('public/nuevo_alumno.html', form=form)

@public_bp.route("/calificaciones")
def calificaciones():
    codigo = request.args.get('codigoAlumno')
    alumno_encontrado = None

    if codigo:
        alumno_encontrado = Alumno.query.filter_by(password=codigo).first()
    return render_template("public/calificaciones.html", alumno=alumno_encontrado)


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


@public_bp.route("/error")
@login_required
def show_error():
    res = 1 / 0
    # posts = Post.get_all()
    # return render_template("public/index.html", posts=posts)
    return "Error"
