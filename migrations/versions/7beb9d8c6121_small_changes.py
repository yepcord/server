"""small changes

Revision ID: 7beb9d8c6121
Revises: 5af66bf76735
Create Date: 2023-07-06 16:26:30.250932

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '7beb9d8c6121'
down_revision = '5af66bf76735'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('guildtemplates', 'updated_at',
               existing_type=mysql.DATETIME(),
               nullable=True)
    op.alter_column('invites', 'max_age',
               existing_type=mysql.BIGINT(display_width=20),
               nullable=True)
    op.alter_column('userdatas', 'flags',
               existing_type=mysql.BIGINT(display_width=20),
               nullable=True)
    op.alter_column('userdatas', 'public_flags',
               existing_type=mysql.BIGINT(display_width=20),
               nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('userdatas', 'public_flags',
               existing_type=mysql.BIGINT(display_width=20),
               nullable=False)
    op.alter_column('userdatas', 'flags',
               existing_type=mysql.BIGINT(display_width=20),
               nullable=False)
    op.alter_column('invites', 'max_age',
               existing_type=mysql.BIGINT(display_width=20),
               nullable=False)
    op.alter_column('guildtemplates', 'updated_at',
               existing_type=mysql.DATETIME(),
               nullable=False)
    # ### end Alembic commands ###
