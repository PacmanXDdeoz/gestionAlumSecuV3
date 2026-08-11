"""add qr support and auth tables

Revision ID: 039e35968cbc
Revises: 
Create Date: 2026-07-26 01:22:16.598105

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '039e35968cbc'
down_revision = None
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


def _column_exists(bind, table_name, column_name, schema):
    if bind.dialect.name == 'postgresql':
        result = bind.execute(sa.text("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = COALESCE(:schema, current_schema())
              AND table_name = :table_name
              AND column_name = :column_name
        """), {'schema': schema, 'table_name': table_name, 'column_name': column_name}).scalar()
        return bool(result)

    result = bind.execute(sa.text('PRAGMA table_info(%s)' % table_name)).fetchall()
    return any(row[1] == column_name for row in result)


def upgrade():
    bind = op.get_bind()
    schema = _get_schema_name(bind)

    if bind.dialect.name == 'postgresql':
        op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS alejandra"))

    if _table_exists(bind, 'alumnos', schema) and not _column_exists(bind, 'alumnos', 'codigo_qr', schema):
        if bind.dialect.name == 'postgresql':
            op.execute(sa.text("ALTER TABLE alejandra.alumnos ADD COLUMN codigo_qr VARCHAR(255)"))
        else:
            op.add_column('alumnos', sa.Column('codigo_qr', sa.String(255), nullable=True), schema=None)

    if _table_exists(bind, 'historial_logs', schema):
        with op.batch_alter_table('historial_logs', schema=schema) as batch_op:
            if bind.dialect.name == 'postgresql':
                try:
                    batch_op.drop_constraint(batch_op.f('fk_historial_docente'), type_='foreignkey')
                except Exception:
                    pass
                batch_op.create_foreign_key(None, 'docentes', ['docente_id'], ['id'], referent_schema=schema)


def downgrade():
    bind = op.get_bind()
    schema = _get_schema_name(bind)

    if _table_exists(bind, 'alumnos', schema) and _column_exists(bind, 'alumnos', 'codigo_qr', schema):
        if bind.dialect.name == 'postgresql':
            op.execute(sa.text("ALTER TABLE alejandra.alumnos DROP COLUMN codigo_qr"))
        else:
            op.drop_column('alumnos', 'codigo_qr', schema=None)

    if _table_exists(bind, 'historial_logs', schema):
        with op.batch_alter_table('historial_logs', schema=schema) as batch_op:
            if bind.dialect.name == 'postgresql':
                try:
                    batch_op.drop_constraint(None, type_='foreignkey')
                except Exception:
                    pass
                batch_op.create_foreign_key(batch_op.f('fk_historial_docente'), 'docentes', ['docente_id'], ['id'], referent_schema=schema, ondelete='SET NULL')
