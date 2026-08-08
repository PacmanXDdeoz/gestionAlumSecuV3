"""add alumno annotations

Revision ID: 8d2b4c5e7f21
Revises: 35d489288e85
Create Date: 2026-08-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8d2b4c5e7f21'
down_revision = '35d489288e85'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE IF NOT EXISTS alejandra.anotaciones_alumno (
        id SERIAL PRIMARY KEY,
        alumno_id INTEGER NOT NULL,
        docente_id INTEGER,
        texto TEXT NOT NULL DEFAULT '',
        creado_en TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
        actualizado_en TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
        CONSTRAINT fk_anotaciones_alumno_alumno
            FOREIGN KEY (alumno_id) REFERENCES alejandra.alumnos(id) ON DELETE CASCADE,
        CONSTRAINT fk_anotaciones_alumno_docente
            FOREIGN KEY (docente_id) REFERENCES alejandra.docentes(id) ON DELETE SET NULL
    );
    """)

    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'alejandra'
              AND indexname = 'ix_anotaciones_alumno_alumno_id'
        ) THEN
            CREATE INDEX ix_anotaciones_alumno_alumno_id
                ON alejandra.anotaciones_alumno (alumno_id);
        END IF;
    END $$;
    """)


def downgrade():
    op.execute("""
    DROP TABLE IF EXISTS alejandra.anotaciones_alumno;
    """)
