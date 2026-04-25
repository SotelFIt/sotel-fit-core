"""add landbot_user_id to clients

Revision ID: 001_add_landbot_user_id
Revises: 
Create Date: 2026-04-18

"""
from alembic import op
import sqlalchemy as sa

revision = '001_add_landbot_user_id'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('clients', sa.Column('landbot_user_id', sa.String(), nullable=True))
    op.create_index('ix_client_landbot', 'clients', ['landbot_user_id'], unique=True)
    op.create_index('ix_client_email_active', 'clients', ['email', 'is_active'])

def downgrade() -> None:
    op.drop_index('ix_client_landbot', table_name='clients')
    op.drop_index('ix_client_email_active', table_name='clients')
    op.drop_column('clients', 'landbot_user_id')
