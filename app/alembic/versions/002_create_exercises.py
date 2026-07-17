"""create exercises table - Biblioteca de Exercicios V1 (LIB-002)

Revision ID: 002_create_exercises
Revises: 001_add_landbot_user_id
Create Date: 2026-07-17

Exclusivamente ADITIVA: cria apenas a tabela exercises + indice unico do slug.
Nenhuma tabela existente e alterada. Sem backfill. Downgrade remove SOMENTE a tabela.
"""
from alembic import op
import sqlalchemy as sa

revision = '002_create_exercises'
down_revision = '001_add_landbot_user_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'exercises',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('primary_muscle', sa.String(), nullable=False),
        sa.Column('secondary_muscles', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('equipment', sa.String(), nullable=False),
        sa.Column(
            'level',
            sa.Enum('iniciante', 'intermediario', 'avancado', name='exercise_level', native_enum=False),
            nullable=False,
        ),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('common_errors', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('cautions', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('approved_substitutions', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('media', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_exercises_slug', 'exercises', ['slug'], unique=True)


def downgrade() -> None:
    # Regra da LIB-002: downgrade so pode remover a tabela (e seu indice).
    op.drop_index('ix_exercises_slug', table_name='exercises')
    op.drop_table('exercises')
