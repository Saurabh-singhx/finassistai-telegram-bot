"""add pkce verifier to google oauth state

Revision ID: f92b7a4859a3
Revises: c74e68e2cb0b
Create Date: 2026-08-09 22:37:08.965515

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.

revision: str = 'f92b7a4859a3'
down_revision: Union[str, Sequence[str], None] = 'c74e68e2cb0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        "google_oauth_states",
        sa.Column(
            "code_verifier",
            sa.String(),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE google_oauth_states
        SET code_verifier = 'legacy-placeholder'
        WHERE code_verifier IS NULL
        """
    )

    op.alter_column(
        "google_oauth_states",
        "code_verifier",
        existing_type=sa.String(),
        nullable=False,
    )
    # ### end Alembic commands ###

def downgrade() -> None:
    op.drop_column("google_oauth_states", "code_verifier")