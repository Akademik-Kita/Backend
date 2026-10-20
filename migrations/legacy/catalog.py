"""create catalog school and recommendation tables

Revision ID: p2_0001
Revises:
"""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "p2_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if not context.is_offline_mode():
        existing = set(sa.inspect(op.get_bind()).get_table_names())
        if "student_profiles" not in existing:
            raise RuntimeError(
                "Jalankan migrasi student_profiles milik akun dan profil terlebih dahulu"
            )
        owned = {
            "regions",
            "institutions",
            "programs",
            "admission_tracks",
            "admission_history",
            "costs",
            "facilities",
            "recommendation_runs",
            "recommendation_items",
        }
        if existing & owned:
            raise RuntimeError(
                "Tabel katalog sudah ada tanpa revision ini; review skema sebelum migrasi"
            )
    op.create_table(
        "regions",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("type IN ('provinsi','kab_kota','kecamatan','kelurahan')"),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["regions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "institutions",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("institution_type", sa.String(length=10), nullable=False),
        sa.Column("ownership", sa.String(length=10), nullable=False),
        sa.Column("npsn_or_code", sa.String(length=40), nullable=True),
        sa.Column("region_id", sa.Uuid(), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accreditation", sa.String(length=20), nullable=False),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("contact", sa.String(length=100), nullable=True),
        sa.Column("data_source", sa.Text(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("ownership IN ('negeri','swasta')"),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180"),
        sa.ForeignKeyConstraint(
            ["region_id"],
            ["regions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("npsn_or_code"),
    )
    op.create_index(
        op.f("ix_institutions_accreditation"), "institutions", ["accreditation"], unique=False
    )
    op.create_index(op.f("ix_institutions_name"), "institutions", ["name"], unique=False)
    op.create_index(
        "ix_institutions_type_region",
        "institutions",
        ["institution_type", "region_id"],
        unique=False,
    )
    op.create_table(
        "recommendation_runs",
        sa.Column("student_profile_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column(
            "input_snapshot",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["student_profile_id"], ["student_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recommendation_runs_student_created",
        "recommendation_runs",
        ["student_profile_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "facilities",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("institution_id", "name"),
    )
    op.create_index(
        op.f("ix_facilities_institution_id"), "facilities", ["institution_id"], unique=False
    )
    op.create_table(
        "programs",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("program_type", sa.String(length=40), nullable=False),
        sa.Column("degree_level", sa.String(length=20), nullable=True),
        sa.Column("accreditation", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "interest_profile",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "required_subjects",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("institution_id", "name"),
    )
    op.create_index(
        op.f("ix_programs_institution_id"), "programs", ["institution_id"], unique=False
    )
    op.create_table(
        "admission_tracks",
        sa.Column("program_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("quota", sa.Integer(), nullable=False),
        sa.Column(
            "rules",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("quota >= 0"),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["programs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_id", "name"),
    )
    op.create_index(
        op.f("ix_admission_tracks_program_id"), "admission_tracks", ["program_id"], unique=False
    )
    op.create_table(
        "costs",
        sa.Column("program_id", sa.Uuid(), nullable=False),
        sa.Column("academic_year", sa.String(length=9), nullable=False),
        sa.Column("entrance_fee", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("tuition_per_period", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("other_fee", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("period_type", sa.String(length=10), nullable=False),
        sa.Column("scholarship_info", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("period_type IN ('bulan','semester')"),
        sa.CheckConstraint("entrance_fee >= 0 AND tuition_per_period >= 0 AND other_fee >= 0"),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["programs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_id", "academic_year"),
    )
    op.create_index(op.f("ix_costs_program_id"), "costs", ["program_id"], unique=False)
    op.create_table(
        "recommendation_items",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("program_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column(
            "score_breakdown",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("chance_low", sa.Float(), nullable=False),
        sa.Column("chance_high", sa.Float(), nullable=False),
        sa.Column(
            "explanation",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("category IN ('ambisius','realistis','aman')"),
        sa.CheckConstraint("chance_low >= 0 AND chance_low <= chance_high AND chance_high <= 100"),
        sa.CheckConstraint("total_score BETWEEN 0 AND 100"),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["programs.id"],
        ),
        sa.ForeignKeyConstraint(["run_id"], ["recommendation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "program_id"),
        sa.UniqueConstraint("run_id", "rank"),
    )
    op.create_table(
        "admission_history",
        sa.Column("admission_track_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("applicants", sa.Integer(), nullable=False),
        sa.Column("accepted", sa.Integer(), nullable=False),
        sa.Column("min_score", sa.Float(), nullable=False),
        sa.Column("avg_score", sa.Float(), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column(
            "score_distribution",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("accepted >= 0 AND applicants >= accepted"),
        sa.CheckConstraint(
            "min_score >= 0 AND min_score <= avg_score AND avg_score <= max_score AND max_score <= 100"
        ),
        sa.ForeignKeyConstraint(
            ["admission_track_id"],
            ["admission_tracks.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("admission_track_id", "year"),
    )


def downgrade():
    op.drop_table("admission_history")
    op.drop_table("recommendation_items")
    op.drop_index(op.f("ix_costs_program_id"), table_name="costs")
    op.drop_table("costs")
    op.drop_index(op.f("ix_admission_tracks_program_id"), table_name="admission_tracks")
    op.drop_table("admission_tracks")
    op.drop_index(op.f("ix_programs_institution_id"), table_name="programs")
    op.drop_table("programs")
    op.drop_index(op.f("ix_facilities_institution_id"), table_name="facilities")
    op.drop_table("facilities")
    op.drop_index("ix_recommendation_runs_student_created", table_name="recommendation_runs")
    op.drop_table("recommendation_runs")
    op.drop_index("ix_institutions_type_region", table_name="institutions")
    op.drop_index(op.f("ix_institutions_name"), table_name="institutions")
    op.drop_index(op.f("ix_institutions_accreditation"), table_name="institutions")
    op.drop_table("institutions")
    op.drop_table("regions")
