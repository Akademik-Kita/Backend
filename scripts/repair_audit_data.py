"""Preview or repair only the known audit data, with an explicit budget value."""

import argparse
import json
from pathlib import Path

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from app.core.database import get_engine
from app.demo import DEMO_USER_ID
from app.models import (
    AdmissionHistory,
    AdmissionTrack,
    Cost,
    Facility,
    Institution,
    Program,
    RecommendationItem,
    StudentProfile,
    User,
)
from machine_learning_recommendation_system.services.importer import load_catalog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--restore-budget", help="Original budget integer, or null for an unset value"
    )
    args = parser.parse_args()
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        raise SystemExit("This repair is only for the configured PostgreSQL database")
    demo = load_catalog("data/schools-demo.json")
    official = load_catalog("data/schools-jakarta-selatan.json")
    school_ids = [school.id for school in demo.schools]
    program_ids = [program.id for school in demo.schools for program in school.programs]
    track_ids = [
        track.id
        for school in demo.schools
        for program in school.programs
        for track in program.tracks
    ]
    with Session(engine) as db, db.begin():
        db.execute(text("SET LOCAL search_path = public"))
        existing_ids = db.scalars(select(User.id).where(User.id != DEMO_USER_ID)).all()
        profiles = db.scalars(
            select(StudentProfile).where(StudentProfile.user_id != DEMO_USER_ID)
        ).all()
        if len(existing_ids) != 1 or len(profiles) != 1:
            raise RuntimeError(
                "Unexpected account/profile count; repair aborted without changing data"
            )
        preview = {
            "existing_accounts_retained": len(existing_ids),
            "existing_profiles_retained": len(profiles),
            "audit_demo_accounts": db.scalar(
                select(func.count()).select_from(User).where(User.id == DEMO_USER_ID)
            ),
            "audit_schools": db.scalar(
                select(func.count()).select_from(Institution).where(Institution.id.in_(school_ids))
            ),
            "official_school_names_to_restore": len(official.schools),
        }
        print(json.dumps(preview))
        if not args.apply:
            return
        if args.restore_budget is None:
            raise ValueError("An explicit original budget is required before applying the repair")
        budget = None if args.restore_budget == "null" else int(args.restore_budget)
        if budget is not None and budget < 0:
            raise ValueError("Budget must be nonnegative")
        backup = [
            {
                column.name: getattr(profile, column.name)
                for column in StudentProfile.__table__.columns
            }
            for profile in profiles
        ]
        backup_path = Path(".audit-backup/20261014-before-repair.json")
        backup_path.parent.mkdir(exist_ok=True)
        if not backup_path.exists():
            backup_path.write_text(
                json.dumps(backup, default=str, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        db.execute(delete(User).where(User.id == DEMO_USER_ID))
        db.flush()
        if db.scalar(
            select(RecommendationItem.id)
            .where(RecommendationItem.program_id.in_(program_ids))
            .limit(1)
        ):
            raise RuntimeError(
                "A retained recommendation references audit programs; transaction rolled back"
            )
        db.execute(
            delete(AdmissionHistory).where(AdmissionHistory.admission_track_id.in_(track_ids))
        )
        db.execute(delete(AdmissionTrack).where(AdmissionTrack.id.in_(track_ids)))
        db.execute(delete(Cost).where(Cost.program_id.in_(program_ids)))
        db.execute(delete(Facility).where(Facility.institution_id.in_(school_ids)))
        db.execute(delete(Program).where(Program.id.in_(program_ids)))
        db.execute(delete(Institution).where(Institution.id.in_(school_ids)))
        for school in official.schools:
            db.execute(
                update(Institution).where(Institution.id == school.id).values(name=school.name)
            )
        db.execute(
            update(StudentProfile)
            .where(StudentProfile.id == profiles[0].id)
            .values(budget_max_per_bulan=budget)
        )
        assert db.scalars(select(User.id).where(User.id != DEMO_USER_ID)).all() == existing_ids
    print("Repair committed: original account/profile retained and original budget restored")


if __name__ == "__main__":
    main()
