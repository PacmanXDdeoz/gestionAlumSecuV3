"""add docentes.rol column

Revision ID: 1a2b3c4d5e6f
Revises: 039e35968cbc
Create Date: 2026-07-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1a2b3c4d5e6f'
down_revision = '039e35968cbc'
branch_labels = None
depends_on = None


def upgrade():
    # Add 'rol' column if it doesn't exist
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'alejandra'
              AND table_name = 'docentes'
              AND column_name = 'rol'
        ) THEN
            ALTER TABLE alejandra.docentes ADD COLUMN rol VARCHAR(20) NOT NULL DEFAULT 'docente';
        END IF;
    END $$;
    """)


def downgrade():
    op.execute("""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'alejandra'
              AND table_name = 'docentes'
              AND column_name = 'rol'
        ) THEN
            ALTER TABLE alejandra.docentes DROP COLUMN rol;
        END IF;
    END $$;
    """)
