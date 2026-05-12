from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slack_user_id", sa.Text, nullable=False),
        sa.Column("slack_channel_id", sa.Text, nullable=False),
        sa.Column("slack_thread_ts", sa.Text, nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("response", sa.Text),
        sa.Column("success", sa.Boolean, default=False),
        sa.Column("started_at", sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column("duration_ms", sa.Integer, default=0),
        sa.Column("input_tokens", sa.Integer, default=0),
        sa.Column("output_tokens", sa.Integer, default=0),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
