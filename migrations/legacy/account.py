"""Auth, profil, dan seed sepuluh mata pelajaran.

Revision ID: p1_0001
Revises:
"""

from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "p1_0001"
down_revision = None
branch_labels = None
depends_on = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
TABLES = (
    "users",
    "student_profiles",
    "subjects",
    "academic_records",
    "achievements",
    "interest_assessments",
)
SUBJECTS = (
    "Matematika",
    "Bahasa Indonesia",
    "Bahasa Inggris",
    "IPA",
    "IPS",
    "Seni Budaya",
    "PJOK",
    "Prakarya",
    "PPKn",
    "Agama",
)


def upgrade():
    if not context.is_offline_mode():
        existing = set(sa.inspect(op.get_bind()).get_table_names())
        if existing & set(TABLES):
            raise RuntimeError(
                "Tabel akun dan profil sudah ada; periksa database demo sebelum migrasi"
            )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(500), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('siswa','orang_tua')"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "student_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("current_school_name", sa.String(200)),
        sa.Column("grade", sa.Integer()),
        sa.Column("domisili_kecamatan", sa.String(120)),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("budget_max_per_bulan", sa.Integer()),
        sa.Column("max_distance_km", sa.Float()),
        sa.Column("preferred_ownership", JSON_TYPE),
        sa.Column("profile_completeness", sa.Integer(), nullable=False),
        sa.CheckConstraint("grade BETWEEN 7 AND 9 OR grade IS NULL"),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90 OR latitude IS NULL"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180 OR longitude IS NULL"),
        sa.CheckConstraint("budget_max_per_bulan >= 0 OR budget_max_per_bulan IS NULL"),
        sa.CheckConstraint("max_distance_km > 0 OR max_distance_km IS NULL"),
        sa.CheckConstraint("profile_completeness BETWEEN 0 AND 100"),
    )
    op.create_table(
        "subjects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("category", sa.String(30), nullable=False),
    )
    op.create_table(
        "academic_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_profile_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject_id", sa.Uuid(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("grade_level", sa.Integer(), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("verification_status", sa.String(20), nullable=False),
        sa.Column("verified_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("student_profile_id", "subject_id", "grade_level", "semester"),
        sa.CheckConstraint("grade_level BETWEEN 7 AND 9"),
        sa.CheckConstraint("semester IN (1,2)"),
        sa.CheckConstraint("score BETWEEN 0 AND 100"),
        sa.CheckConstraint("verification_status IN ('belum','diverifikasi','ditolak')"),
    )
    op.create_index(
        "ix_academic_records_student_profile_id", "academic_records", ["student_profile_id"]
    )
    op.create_table(
        "achievements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_profile_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "level IN ('sekolah','kecamatan','kota','provinsi','nasional','internasional')"
        ),
    )
    op.create_index("ix_achievements_student_profile_id", "achievements", ["student_profile_id"])
    op.create_table(
        "interest_assessments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_profile_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("instrument_version", sa.String(60), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scores", JSON_TYPE, nullable=False),
    )
    op.create_index(
        "ix_interest_assessments_student_profile_id", "interest_assessments", ["student_profile_id"]
    )

    # ORM tidak diperlukan untuk seed; UUID deterministik menjaga kesesuaian impor.
    subjects = sa.table(
        "subjects",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("category", sa.String()),
    )
    op.bulk_insert(
        subjects,
        [
            {
                "id": uuid5(NAMESPACE_URL, "akademikkita/subject/" + name),
                "name": name,
                "category": "inti",
            }
            for name in SUBJECTS
        ],
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            for role in ("anon", "authenticated"):
                op.execute(
                    "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '"
                    + role
                    + "') THEN REVOKE ALL ON TABLE \""
                    + table
                    + '" FROM "'
                    + role
                    + '"; END IF; END $$;'
                )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("Downgrade tabel siswa ditolak karena berisi data pribadi")
    for table in reversed(TABLES):
        op.drop_table(table)
