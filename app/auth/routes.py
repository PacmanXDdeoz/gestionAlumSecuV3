from flask import render_template, redirect, url_for, request, flash
from flask_login import current_user, login_user, logout_user
from urllib.parse import urlparse

from app import login_manager
from . import auth_bp
from .decorators import admin_required
from .forms import SignupForm, LoginForm
from .models import Docente, Rol


@auth_bp.route("/signup/", methods=["GET", "POST"])
@auth_bp.route("/docente/nuevo", methods=["GET", "POST"])
@admin_required
def signup():
    """Solo el admin puede crear nuevos docentes."""
    form = SignupForm()
    error = None
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        password = form.password.data
        apellidos = form.apellidos.data
        docente = Docente.get_by_email(email)
        if docente is not None:
            error = f'El email {email} ya está siendo utilizado por otro usuario'
        else:
            docente = Docente(name=name, email=email, apellidos=apellidos)
            docente.set_password(password)
            docente.save()
            flash(f'Docente {name} creado exitosamente.', 'success')
            return redirect(url_for('admin.list_docentes'))
    return render_template("auth/signup_form.html", form=form, error=error)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('public.docente_panel'))
    form = LoginForm()
    error = None
    if form.validate_on_submit():
        docente = Docente.get_by_email(form.email.data)
        if docente is None or not docente.check_password(form.password.data):
            error = 'Email o contraseña incorrectos.'
        elif not docente.estatus:
            error = 'Tu cuenta está desactivada. Contacta al administrador.'
        elif not Rol.es_valido(docente.rol):
            error = 'Tu cuenta tiene un rol no autorizado. Contacta al administrador.'
        else:
            login_user(docente, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('public.docente_panel')
            return redirect(next_page)
    return render_template('auth/login_form.html', form=form, error=error)


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('public.home'))


@login_manager.user_loader
def load_user(user_id):
    return Docente.get_by_id(int(user_id))
