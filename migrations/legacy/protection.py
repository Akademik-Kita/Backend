"""Cegah akses tidak disengaja melalui Supabase Data API.

Revision ID: p2_0002
Revises: p2_0001
"""

from alembic import op

revision = "p2_0002"
down_revision = "p2_0001"
branch_labels = None
depends_on = None


OWNED = (
    "regions",
    "institutions",
    "programs",
    "admission_tracks",
    "admission_history",
    "costs",
    "facilities",
    "recommendation_runs",
    "recommendation_items",
)


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in OWNED:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        for role in ("anon", "authenticated"):
            # Role ini ada di Supabase, tetapi belum tentu ada di PostgreSQL biasa.
            op.execute(
                "DO $secure$ BEGIN "
                f"IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
                f'REVOKE ALL ON TABLE "{table}" FROM "{role}"; '
                "END IF; END $secure$;"
            )


def downgrade():
    # Rollback fitur lain tidak boleh membuka akses Data API ke hasil pribadi siswa.
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError(
            "RLS tidak dinonaktifkan otomatis; review rollback keamanan secara manual"
        )
