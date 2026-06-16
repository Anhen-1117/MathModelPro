"""initial_schema

Revision ID: cb12fd76113e
Revises: 
Create Date: 2026-06-11 19:05:10.400305

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb12fd76113e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 确保 literature 列存在（新增于 2026-06-13）
    try:
        op.execute("ALTER TABLE tasks ADD COLUMN literature JSON DEFAULT '[]'")
    except Exception:
        pass  # 列已存在则忽略


def downgrade() -> None:
    """Downgrade schema."""
    # SQLite 不支持 DROP COLUMN，跳过
    pass
