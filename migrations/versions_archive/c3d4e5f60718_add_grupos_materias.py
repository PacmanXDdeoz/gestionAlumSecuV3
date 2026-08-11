"""add grupos_materias (curriculum por grupo)

Revision ID: c3d4e5f60718
Revises: 8d2b4c5e7f21
Create Date: 2026-08-08 00:00:00.000000

Crea la tabla de asociación ``alejandra.grupos_materias`` que define el
currículum de cada grupo: qué materias se imparten en cada uno. La boleta
de un alumno mostrará únicamente las materias de su grupo.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f60718'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE IF NOT EXISTS alejandra.grupos_materias (
        grupo_id INTEGER NOT NULL,
        materia_id INTEGER NOT NULL,
        PRIMARY KEY (grupo_id, materia_id),
        CONSTRAINT fk_grupos_materias_grupo
            FOREIGN KEY (grupo_id) REFERENCES alejandra.grupos(id) ON DELETE CASCADE,
        CONSTRAINT fk_grupos_materias_materia
            FOREIGN KEY (materia_id) REFERENCES alejandra.materias(id) ON DELETE CASCADE
    );
    """)


def downgrade():
    op.execute("""
    DROP TABLE IF EXISTS alejandra.grupos_materias;
    """)
