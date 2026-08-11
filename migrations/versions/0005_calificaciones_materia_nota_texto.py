"""calificaciones_materia nota_texto

Revision ID: 0005_nota_texto
Revises: 0004_alumno_tutor
Create Date: 2026-08-11

Añade ``alejandra.calificaciones_materia.nota_texto`` (nullable): la nota o
comentario que el docente comparte con el alumno para una materia concreta.
Al vivir en el registro (alumno, materia) cada materia tiene hasta una nota,
que la boleta pública muestra junto a la calificación. Nullable: no afecta a
los registros ya existentes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_nota_texto'
down_revision = '0004_alumno_tutor'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'calificaciones_materia',
        sa.Column('nota_texto', sa.Text(), nullable=True),
        schema='alejandra',
    )


def downgrade():
    op.drop_column('calificaciones_materia', 'nota_texto', schema='alejandra')
