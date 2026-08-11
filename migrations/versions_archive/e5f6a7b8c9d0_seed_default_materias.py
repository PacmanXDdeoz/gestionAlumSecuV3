"""seed default materias

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f60718
Create Date: 2026-08-09 01:00:00.000000

Siembra las materias por defecto del plantel en ``alejandra.materias``
para que las bases recién migradas tengan el catálogo completo sin
pasos manuales. Idempotente: usa ``ON CONFLICT (nombre) DO NOTHING``
(la columna ``nombre`` es UNIQUE), así que no duplica ni modifica
materias ya existentes.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'c3d4e5f60718'
branch_labels = None
depends_on = None

# Materias por defecto (coinciden con app.models.MATERIAS_DEFAULT).
MATERIAS_DEFAULT = [
    ('Español', 'Lengua y literatura'),
    ('Matemáticas', 'Matemáticas'),
    ('Biología', 'Biología'),
    ('Química', 'Química'),
    ('Física', 'Física'),
    ('Historia', 'Historia'),
    ('Formación cívica y Ética', 'Formación cívica y Ética'),
    ('Geografía', 'Geografía'),
    ('Inglés', 'Inglés'),
    ('Artes (música y teatro)', 'Artes: música y teatro'),
    ('Tecnologías (talleres)', 'Tecnologías: talleres'),
    ('Fomento a la lectura', 'Fomento a la lectura'),
    ('Educación Física', 'Educación Física'),
]


def upgrade():
    bind = op.get_bind()
    for nombre, descripcion in MATERIAS_DEFAULT:
        bind.execute(
            sa.text(
                "INSERT INTO alejandra.materias (nombre, descripcion) "
                "VALUES (:nombre, :descripcion) ON CONFLICT (nombre) DO NOTHING"
            ),
            {'nombre': nombre, 'descripcion': descripcion},
        )


def downgrade():
    # No eliminamos materias en el downgrade: podrían tener relaciones
    # (docentes, grupos, calificaciones) y el borrado sería destructivo.
    pass
