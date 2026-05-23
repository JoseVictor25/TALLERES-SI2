"""merge heads

Revision ID: merge_heads_rev
Revises: 67a2acf835af, 75d50c36d769
Create Date: 2026-05-21 17:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_heads_rev'
down_revision: Union[str, Sequence[str], None] = ('67a2acf835af', '75d50c36d769')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
