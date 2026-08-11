"""alumno tutor_id

Revision ID: 0004_alumno_tutor
Revises: 0003_horarios_grupo
Create Date: 2026-08-10

Añade ``alejandra.alumnos.tutor_id`` (nullable, FK a ``alejandra.docentes.id``):
el profesor/tutor asignado a cada alumno. La vista de edición del docente
``/docente/alumno/<id>/editar`` lo expone como un select de los docentes
registrados en la plataforma. Al ser nullable no afecta a los alumnos ya
existentes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_alumno_tutor'
down_revision = '0003_horarios_grupo'
branch_labels = None
depends_on = None

_FK_NAME = 'fk_alumnos_tutor'


def upgrade():
    # Nullable: los alumnos existentes no tienen tutor asignado todavía.
    op.add_column(
        'alumnos',
        sa.Column('tutor_id', sa.Integer(), nullable=True),
        schema='alejandra',
    )
    op.create_foreign_key(
        _FK_NAME, 'alumnos', 'docentes',
        ['tutor_id'], ['id'],
        source_schema='alejandra', referent_schema='alejandra',
    )


def downgrade():
    op.drop_constraint(_FK_NAME, 'alumnos', type_='foreignkey', schema='alejandra')
    op.drop_column('alumnos', 'tutor_id', schema='alejandra')
