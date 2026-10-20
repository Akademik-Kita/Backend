
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from crud_database.models import StudentProfile


def row_for_user(db: Session, user_id: UUID) -> Optional[dict]:
    """Mengambil profil siswa berdasarkan user_id."""
    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == user_id)
        .first()
    )

    if profile is None:
        return None

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "latitude": profile.latitude,
        "longitude": profile.longitude,
    }


def load_student(db: Session, user_id: UUID) -> Any:
    """Mengambil profil siswa berdasarkan user_id."""
    return (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == user_id)
        .first()
    )


def load_location(db: Session, user_id: Optional[UUID]) -> Any:
    """Mengambil lokasi siswa berdasarkan user_id."""
    if not user_id:
        return None

    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == user_id)
        .first()
    )

    if profile is None:
        return None

    if profile.latitude is None or profile.longitude is None:
        return None

    return profile
