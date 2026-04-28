import logging

from flask import abort, render_template, redirect, url_for, request, current_app
from flask_login import current_user

# from app.models import Post, Comment
from app.models import Alumno
from . import public_bp
# from .forms import CommentForm

logger = logging.getLogger(__name__)


@public_bp.route("/")
def index():
    alumno = Alumno.query.all()
    return render_template("public/index.html", alumno=alumno)

@public_bp.route("/calificaciones")
def calificaciones():
    codigo = request.args.get('codigoAlumno')
    alumno_encontrado = None

    if codigo:
        alumno_encontrado = Alumno.query.filter_by(password=codigo).first()
    return render_template("public/calificaciones.html", alumno=alumno_encontrado)


@public_bp.route("/error")
def show_error():
    res = 1 / 0
    # posts = Post.get_all()
    # return render_template("public/index.html", posts=posts)
    return "Error"
