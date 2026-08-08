"""Create missing tables for the Alejandra schema

Revision ID: fe5a6f9c7d21
Revises: 039e35968cbc
Create Date: 2026-07-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'fe5a6f9c7d21'
down_revision = '039e35968cbc'
branch_labels = None
depends_on = None


def _get_schema_name(bind):
    if bind.dialect.name == 'postgresql':
        return 'alejandra'
    return None


def _table_exists(bind, table_name, schema):
    if bind.dialect.name == 'postgresql':
        result = bind.execute(sa.text("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = COALESCE(:schema, current_schema())
              AND table_name = :table_name
        """), {'schema': schema, 'table_name': table_name}).scalar()
        return bool(result)

    result = bind.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name"), {'table_name': table_name}).scalar()
    return bool(result)


def upgrade():
    bind = op.get_bind()
    schema = _get_schema_name(bind)

    if bind.dialect.name == 'postgresql':
        op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS alejandra"))

    if not _table_exists(bind, 'grupos', schema):
        op.create_table(
            'grupos',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('grado', sa.String(length=1), nullable=False),
            sa.Column('grupo', sa.String(length=1), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            schema=schema,
        )

    if not _table_exists(bind, 'docentes', schema):
        op.create_table(
            'docentes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('nombre', sa.String(length=100), nullable=False),
            sa.Column('apellidos', sa.String(length=100), nullable=False),
            sa.Column('email', sa.String(length=150), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('estatus', sa.Boolean(), nullable=True),
            sa.Column('creado_en', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email'),
            schema=schema,
        )

    if not _table_exists(bind, 'alumnos', schema):
        op.create_table(
            'alumnos',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=50), nullable=False),
            sa.Column('lastname_p', sa.String(length=50), nullable=False),
            sa.Column('lastname_m', sa.String(length=50), nullable=False),
            sa.Column('group_id', sa.Integer(), nullable=False),
            sa.Column('genero', sa.String(length=10), nullable=False),
            sa.Column('status', sa.Boolean(), nullable=False),
            sa.Column('codigo_qr', sa.String(length=255), nullable=True),
            sa.Column('codigo_barras', sa.String(length=255), nullable=True),
            sa.Column('pass', sa.String(length=10), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('codigo_qr'),
            sa.UniqueConstraint('codigo_barras'),
            schema=schema,
        )
        op.create_foreign_key(
            None,
            'alumnos',
            'grupos',
            ['group_id'],
            ['id'],
            source_schema=schema,
            referent_schema=schema,
        )

    if not _table_exists(bind, 'calificaciones', schema):
        op.create_table(
            'calificaciones',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('alumnos_id', sa.Integer(), nullable=False),
            sa.Column('español', sa.Numeric(), nullable=True),
            sa.Column('matematicas', sa.Numeric(), nullable=True),
            sa.Column('ciencias', sa.Numeric(), nullable=True),
            sa.Column('geografia', sa.Numeric(), nullable=True),
            sa.Column('historia', sa.Numeric(), nullable=True),
            sa.Column('f_civica', sa.Numeric(), nullable=True),
            sa.Column('ingles', sa.Numeric(), nullable=True),
            sa.Column('artes', sa.Numeric(), nullable=True),
            sa.Column('f_español', sa.Numeric(), nullable=True),
            sa.Column('f_matematicas', sa.Numeric(), nullable=True),
            sa.Column('tecnologia', sa.Numeric(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            schema=schema,
        )
        op.create_foreign_key(
            None,
            'calificaciones',
            'alumnos',
            ['alumnos_id'],
            ['id'],
            source_schema=schema,
            referent_schema=schema,
        )

    if not _table_exists(bind, 'historial_logs', schema):
        op.create_table(
            'historial_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('docente_id', sa.Integer(), nullable=True),
            sa.Column('accion', sa.String(length=20), nullable=False),
            sa.Column('tabla_afectada', sa.String(length=50), nullable=False),
            sa.Column('registro_afectado_id', sa.Integer(), nullable=False),
            sa.Column('detalles', sa.Text(), nullable=True),
            sa.Column('fecha_accion', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            schema=schema,
        )
        op.create_foreign_key(
            None,
            'historial_logs',
            'docentes',
            ['docente_id'],
            ['id'],
            source_schema=schema,
            referent_schema=schema,
        )

    if not _table_exists(bind, 'blog_user', None):
        op.create_table(
            'blog_user',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=80), nullable=False),
            sa.Column('email', sa.String(length=256), nullable=False),
            sa.Column('password', sa.String(length=128), nullable=False),
            sa.Column('is_admin', sa.Boolean(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email'),
        )


def downgrade():
    bind = op.get_bind()
    schema = _get_schema_name(bind)

    for table_name in ['historial_logs', 'calificaciones', 'alumnos', 'docentes', 'grupos']:
        if _table_exists(bind, table_name, schema):
            op.drop_table(table_name, schema=schema)

    if _table_exists(bind, 'blog_user', None):
        op.drop_table('blog_user')
