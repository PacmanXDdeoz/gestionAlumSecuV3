from flask import render_template, redirect, url_for, request
from flask_login import current_user, login_user, logout_user
from urllib.parse import urlparse

from app import login_manager
from . import auth_bp
from .forms import SignupForm, LoginForm
from .models import Docente


@auth_bp.route("/signup/", methods=["GET", "POST"])
def show_signup_form():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    if not getattr(current_user, 'is_admin', False):
        return redirect(url_for('public.calificaciones'))

    form = SignupForm()
    error = None
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        password = form.password.data
        docente = Docente.get_by_email(email)
        if docente is not None:
            error = f'El email {email} ya está siendo utilizado por otro usuario'
        else:
            docente = Docente(name=name, email=email)
            docente.set_password(password)
            docente.save()
            login_user(docente, remember=True)
            next_page = request.args.get('next', None)
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('public.calificaciones')
            return redirect(next_page)
    return render_template("auth/signup_form.html", form=form, error=error)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('public.calificaciones'))
    form = LoginForm()
    if form.validate_on_submit():
        docente = Docente.get_by_email(form.email.data)
        if docente is not None and docente.check_password(form.password.data):
            login_user(docente, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('public.calificaciones')
            return redirect(next_page)
    return render_template('auth/login_form.html', form=form)


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('public.calificaciones'))


@login_manager.user_loader
def load_user(user_id):
    return Docente.get_by_id(int(user_id))
