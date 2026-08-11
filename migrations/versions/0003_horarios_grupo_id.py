"""horarios grupo_id

Revision ID: 0003_horarios_grupo
Revises: 0002_rol_fk
Create Date: 2026-08-10

Añade ``alejandra.horarios.grupo_id``: cada entrada del horario queda ligada
al grupo donde el docente imparte esa materia. Es la fuente de verdad para
filtrar el roster del docente (solo alumnos de sus grupos) y para mostrar
el grupo en las tarjetas del horario del panel.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_horarios_grupo'
down_revision = '0002_rol_fk'
branch_labels = None
depends_on = None

_FK_NAME = 'fk_horarios_grupo'


def upgrade():
    # Nullable: los horarios existentes no tienen grupo asignado todavía.
    op.add_column(
        'horarios',
        sa.Column('grupo_id', sa.Integer(), nullable=True),
        schema='alejandra',
    )
    op.create_foreign_key(
        _FK_NAME, 'horarios', 'grupos',
        ['grupo_id'], ['id'],
        source_schema='alejandra', referent_schema='alejandra',
    )


def downgrade():
    op.drop_constraint(_FK_NAME, 'horarios', type_='foreignkey', schema='alejandra')
    op.drop_column('horarios', 'grupo_id', schema='alejandra')
