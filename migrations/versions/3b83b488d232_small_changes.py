"""small changes

Revision ID: 3b83b488d232
Revises: 7beb9d8c6121
Create Date: 2023-07-07 17:45:37.644372

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '3b83b488d232'
down_revision = '7beb9d8c6121'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('messages', 'message_reference',
               existing_type=mysql.LONGTEXT(charset='utf8mb4', collation='utf8mb4_bin'),
               nullable=True)
    op.add_column('usernotes', sa.Column('text', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('usernotes', 'text')
    op.alter_column('messages', 'message_reference',
               existing_type=mysql.LONGTEXT(charset='utf8mb4', collation='utf8mb4_bin'),
               nullable=False)
    # ### end Alembic commands ###