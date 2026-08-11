"""Comandos personalizados de Flask CLI.

Registrados en ``create_app``:

* ``flask seed`` — puebla la BD con datos de prueba (grupos, docentes,
  alumnos y horarios con grupo). Todos los docentes de prueba se crean
  con rol = 2 (docente).
* ``flask regenerate-qrs`` — regenera los QRs de todos los alumnos con el
  formato de URL actual (requiere PUBLIC_BASE_URL en .env) y elimina los
  PNGs huérfanos de alumnos que ya no existen en la BD.
* ``flask reset-password`` — busca al docente administrador y le asigna una
  contraseña conocida (por defecto ``Admin2026!``).
"""
import datetime

import click
from flask.cli import with_appcontext

from app import db
from app.auth.models import Docente, ROL_DOCENTE_ID, Rol
from app.models import Alumno, Grupos, Horario, Materia, MATERIAS_DEFAULT
from app.utils.codes import generar_codigo

_GRUPOS_SEED = [
    ('1', 'A'), ('1', 'B'),
    ('2', 'A'), ('2', 'B'),
    ('3', 'A'), ('3', 'B'),
]


def _asegurar_materias():
    Materia.seed_materias()


def _asegurar_roles():
    Rol.seed_defaults()


def _asegurar_grupos():
    """Crea los grupos base si no existen y les asigna el currículum completo."""
    materias = Materia.query.all()
    creados = 0
    for grado, grupo in _GRUPOS_SEED:
        existente = Grupos.query.filter_by(grado=grado, grupo=grupo).first()
        if existente is None:
            g = Grupos(grado=grado, grupo=grupo)
            g.materias = materias  # currículum completo
            g.save()
            creados += 1
    return creados


def _asegurar_docentes(cantidad, password):
    """Crea docentes de prueba con rol = 2 (docente, catálogo alejandra.rol)."""
    materias = Materia.query.all()
    if not materias:
        click.echo('  No hay materias; omite la asignación de materias.')
    creados = 0
    for i in range(1, cantidad + 1):
        email = f'docente{i}@escuela.test'
        if Docente.get_by_email(email) is not None:
            continue
        d = Docente(
            name=f'Docente {i}',
            apellidos='Prueba',
            email=email,
            rol=ROL_DOCENTE_ID,  # ← rol = 2 (docente)
        )
        d.set_password(password)
        if materias:
            # Asigna 2-3 materias por docente (rotación simple)
            d.materias = materias[(i - 1) % len(materias): (i - 1) % len(materias) + 3]
        d.save()
        creados += 1
    return creados


def _asegurar_alumnos(cantidad):
    """Crea alumnos de prueba distribuidos en los grupos existentes."""
    grupos = Grupos.query.order_by(Grupos.grado, Grupos.grupo).all()
    if not grupos:
        click.echo('  No hay grupos; crea primero grupos con --grupos o en el admin.')
        return 0
    nombres = ['Ana', 'Luis', 'María', 'José', 'Sofía', 'Carlos',
               'Valentina', 'Diego', 'Regina', 'Emiliano', 'Ximena', 'Mateo']
    creados = 0
    for i in range(cantidad):
        codigo = generar_codigo()
        while Alumno.query.filter_by(password=codigo).first():
            codigo = generar_codigo()
        grupo = grupos[i % len(grupos)]
        a = Alumno(
            name=nombres[i % len(nombres)],
            lastname_p=f'ApellidoP{i + 1}',
            lastname_m=f'ApellidoM{i + 1}',
            group_id=grupo.id,
            genero='M' if i % 2 == 0 else 'F',
            password=codigo,
            status=True,
        )
        a.save()
        creados += 1
    return creados


def _asegurar_horarios():
    """Crea horarios (con grupo) para los docentes de prueba sin horario.

    Cada docente recibe una entrada por materia (máx. 3), asignada a un
    grupo del catálogo. Es la fuente de verdad que limita el roster del
    docente a los alumnos de sus grupos.
    """
    docentes = Docente.query.filter(Docente.email.like('docente%@escuela.test')).all()
    grupos = Grupos.query.order_by(Grupos.grado, Grupos.grupo).all()
    creados = 0
    for d in docentes:
        if d.horarios:
            continue
        materias = d.materias.all()
        if not materias or not grupos:
            continue
        for idx, m in enumerate(materias[:3]):
            g = grupos[idx % len(grupos)]
            db.session.add(Horario(
                docente_id=d.id,
                materia_id=m.id,
                grupo_id=g.id,
                dia_semana=(idx % 5) + 1,
                hora_inicio=datetime.time(7 + idx, 0),
                hora_fin=datetime.time(8 + idx, 0),
                salon=f'A{idx + 1}',
            ))
        creados += 1
    db.session.commit()
    return creados


@click.command('seed')
@click.option('--docentes', default=5, show_default=True,
              help='Número de docentes de prueba (todos con rol = 2)')
@click.option('--alumnos', default=18, show_default=True,
              help='Número de alumnos de prueba')
@click.option('--password', default='Docente123', show_default=True,
              help='Contraseña de los docentes de prueba')
@click.option('--force', is_flag=True,
              help='Fuerza la creación de alumnos aunque la BD ya tenga datos')
@with_appcontext
def seed_command(docentes, alumnos, password, force):
    """Puebla la BD con datos de prueba (grupos, docentes rol=2 y alumnos)."""
    click.echo('Sembrando datos de prueba…')
    _asegurar_roles()
    click.echo('  ✓ Roles del catálogo listos.')
    _asegurar_materias()
    click.echo(f'  ✓ Materias listas ({Materia.query.count()}).')
    n = _asegurar_grupos()
    click.echo(f'  ✓ Grupos listos ({Grupos.query.count()}, nuevos: {n}).')
    n = _asegurar_docentes(docentes, password)
    click.echo(f'  ✓ Docentes con rol=2 listos ({Docente.query.count()}, nuevos: {n}).')
    n = _asegurar_horarios()
    click.echo(f'  ✓ Horarios con grupo listos ({Horario.query.count()}, nuevos: {n}).')
    if Alumno.query.count() > 0 and not force:
        click.echo(f'  ⏭  Alumnos ya existentes ({Alumno.query.count()}); usa --force '
                   f'para añadir {alumnos} más.')
    else:
        n = _asegurar_alumnos(alumnos)
        click.echo(f'  ✓ Alumnos listos ({Alumno.query.count()}, nuevos: {n}).')
    click.echo(f'\nListo. Credenciales de docentes: docente1@escuela.test … '
               f'docente{docentes}@escuela.test / {password}')


@click.command('regenerate-qrs')
@with_appcontext
def regenerate_qrs_command():
    """Regenera el QR de todos los alumnos con el formato de URL actual.

    Los QRs generados antes de este cambio codificaban el ID crudo o el
    código de acceso; los nuevos codifican la URL absoluta ``/buscar/<id>``
    para el escaneo nativo con el celular. Requiere PUBLIC_BASE_URL en .env
    (o ejecutarlo dentro de un request, p. ej. en el servidor).

    Además elimina los PNGs huérfanos de la carpeta de QRs: archivos de
    alumnos que ya no existen en la BD (p. ej. tras una limpieza de la
    tabla ``alumnos``), de modo que la carpeta refleje siempre el estado
    real y nunca muestre QRs de alumnos eliminados.
    """
    import re

    from app.utils.qr import qr_codes_folder

    alumnos = Alumno.query.all()
    if alumnos:
        for a in alumnos:
            a.generate_qr_code()
        click.echo(f'✓ QRs regenerados para {len(alumnos)} alumno(s).')
    else:
        click.echo('No hay alumnos registrados.')

    # ── Sweep de QRs huérfanos ─────────────────────────────────────
    # Misma resolución de carpeta que Alumno.generate_qr_code (fuente
    # única: app.utils.qr.qr_codes_folder).
    carpeta = qr_codes_folder()
    if not carpeta.is_dir():
        click.echo('No existe la carpeta de QRs; nada que limpiar.')
        return

    ids_existentes = {a.id for a in alumnos}
    patron = re.compile(r'^alumno_(\d+)\.png$')
    eliminados = 0
    for archivo in carpeta.glob('alumno_*.png'):
        m = patron.match(archivo.name)
        if m and int(m.group(1)) not in ids_existentes:
            archivo.unlink()
            eliminados += 1

    if eliminados:
        click.echo(f'🗑  Eliminados {eliminados} QR(s) huérfano(s) de alumnos ya eliminados.')
    else:
        click.echo('No hay QRs huérfanos que limpiar.')


@click.command('reset-password')
@click.option('--email', default='admin@example.com', show_default=True,
              help='Email del docente administrador')
@click.option('--password', default='Admin2026!', show_default=True,
              help='Nueva contraseña')
@with_appcontext
def reset_password_command(email, password):
    """Asigna una contraseña conocida al docente administrador."""
    docente = Docente.get_by_email(email)
    if docente is None:
        # Fallback: buscar por nombre parecido a 'admin'
        docente = Docente.query.filter(Docente.nombre.ilike('%admin%')).first()
    if docente is None:
        raise click.ClickException(
            f'No se encontró un docente con email {email} (ni por nombre "admin").'
        )
    docente.set_password(password)
    docente.save()
    click.echo(f'✓ Contraseña actualizada para {docente.email} (rol {docente.rol}).')
    click.echo(f'  Puedes iniciar sesión con: {docente.email} / {password}')
