"""docentes rol integer fk

Revision ID: 0002_rol_fk
Revises: 0001_initial
Create Date: 2026-08-08 20:20:24.350425

Convierte la columna ``docentes.rol`` de VARCHAR ('admin'/'docente') a INTEGER
con FK al catálogo ``alejandra.rol`` (1=admin, 2=docente). Los datos existentes
se migran de forma explícita (no se puede castear 'admin' a entero).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_rol_fk'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

_FK_NAME = 'fk_docentes_rol'


def upgrade():
    bind = op.get_bind()

    # 1) Convertir valores existentes: 'admin' → 1, 'docente' → 2.
    #    También tolera valores ya numéricos ('1', '2') por seguridad.
    bind.execute(sa.text("""
        UPDATE alejandra.docentes
        SET rol = CASE
            WHEN rol = 'admin' THEN 1
            WHEN rol = 'docente' THEN 2
            WHEN rol ~ '^[0-9]+$' THEN CAST(rol AS INTEGER)
            ELSE 2
        END
    """))

    # 2) Cambiar el tipo de columna a INTEGER. PostgreSQL no castea varchar →
    #    integer automáticamente (ni el dato ni el DEFAULT), así que se usa
    #    USING explícito y se reemplaza el DEFAULT por 2 (docente).
    bind.execute(sa.text("ALTER TABLE alejandra.docentes ALTER COLUMN rol DROP DEFAULT"))
    bind.execute(sa.text("""
        ALTER TABLE alejandra.docentes
        ALTER COLUMN rol TYPE INTEGER USING rol::integer
    """))
    bind.execute(sa.text("ALTER TABLE alejandra.docentes ALTER COLUMN rol SET DEFAULT 2"))

    # 3) Añadir la FK al catálogo de roles.
    op.create_foreign_key(
        _FK_NAME, 'docentes', 'rol',
        ['rol'], ['id'], source_schema='alejandra', referent_schema='alejandra'
    )


def downgrade():
    bind = op.get_bind()

    op.drop_constraint(_FK_NAME, 'docentes', type_='foreignkey', schema='alejandra')

    bind.execute(sa.text("ALTER TABLE alejandra.docentes ALTER COLUMN rol DROP DEFAULT"))
    op.alter_column('docentes', 'rol',
                    existing_type=sa.Integer(),
                    type_=sa.VARCHAR(length=20),
                    existing_nullable=False,
                    schema='alejandra')
    bind.execute(sa.text("ALTER TABLE alejandra.docentes ALTER COLUMN rol SET DEFAULT 'docente'"))

    bind.execute(sa.text("""
        UPDATE alejandra.docentes
        SET rol = CASE
            WHEN rol = 1 THEN 'admin'
            WHEN rol = 2 THEN 'docente'
            ELSE 'docente'
        END
    """))
