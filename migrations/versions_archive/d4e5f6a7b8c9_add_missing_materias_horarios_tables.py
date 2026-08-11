"""add missing materias/horarios tables for alejandra schema

Revision ID: d4e5f6a7b8c9
Revises: 8d2b4c5e7f21
Create Date: 2026-08-09 00:00:00.000000

Las migraciones originales creaban solo grupos, docentes, alumnos,
calificaciones e historial_logs. El modelo además define materias,
materias_docentes, horarios y calificaciones_materia, que la migración
de grupos_materias (c3d4e5f60718) requiere como pre-requisito.
Esta migración crea las tablas faltantes y se inserta en la cadena
ANTES de c3d4e5f60718 (su down_revision pasa a apuntar aquí).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = '8d2b4c5e7f21'
branch_labels = None
depends_on = None


def upgrade():
    # ── alejandra.materias ──────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS alejandra.materias (
        id SERIAL PRIMARY KEY,
        nombre VARCHAR(100) NOT NULL UNIQUE,
        descripcion TEXT
    );
    """)

    # ── alejandra.materias_docentes (asociación Docente ↔ Materia) ──
    op.execute("""
    CREATE TABLE IF NOT EXISTS alejandra.materias_docentes (
        docente_id INTEGER NOT NULL,
        materia_id INTEGER NOT NULL,
        PRIMARY KEY (docente_id, materia_id),
        CONSTRAINT fk_materias_docentes_docente
            FOREIGN KEY (docente_id) REFERENCES alejandra.docentes(id) ON DELETE CASCADE,
        CONSTRAINT fk_materias_docentes_materia
            FOREIGN KEY (materia_id) REFERENCES alejandra.materias(id) ON DELETE CASCADE
    );
    """)

    # ── alejandra.horarios ──────────────────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS alejandra.horarios (
        id SERIAL PRIMARY KEY,
        docente_id INTEGER NOT NULL,
        materia_id INTEGER NOT NULL,
        dia_semana INTEGER NOT NULL,
        hora_inicio TIME NOT NULL,
        hora_fin TIME NOT NULL,
        salon VARCHAR(20),
        CONSTRAINT fk_horarios_docente
            FOREIGN KEY (docente_id) REFERENCES alejandra.docentes(id) ON DELETE CASCADE,
        CONSTRAINT fk_horarios_materia
            FOREIGN KEY (materia_id) REFERENCES alejandra.materias(id) ON DELETE CASCADE
    );
    """)

    # ── alejandra.calificaciones_materia ────────────────────────────
    op.execute("""
    CREATE TABLE IF NOT EXISTS alejandra.calificaciones_materia (
        id SERIAL PRIMARY KEY,
        alumnos_id INTEGER NOT NULL,
        materia_id INTEGER NOT NULL,
        calificacion NUMERIC(5, 2),
        periodo VARCHAR(50),
        creado_en TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
        CONSTRAINT fk_calificaciones_materia_alumno
            FOREIGN KEY (alumnos_id) REFERENCES alejandra.alumnos(id) ON DELETE CASCADE,
        CONSTRAINT fk_calificaciones_materia_materia
            FOREIGN KEY (materia_id) REFERENCES alejandra.materias(id) ON DELETE CASCADE
    );
    """)


def downgrade():
    for table in ['calificaciones_materia', 'horarios', 'materias_docentes', 'materias']:
        op.execute(f"DROP TABLE IF EXISTS alejandra.{table};")
