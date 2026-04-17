from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Registration


def next_bib_number(db: Session) -> str:
    while True:
        value = db.execute(
            text(
                """
                UPDATE sequences
                SET next_value = next_value + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE name = :name
                RETURNING next_value - 1
                """
            ),
            {"name": "bib_number"},
        ).scalar_one()
        bib_number = f"{settings.bib_prefix}-{value}"

        exists = db.query(Registration.id).filter(Registration.bib_number == bib_number).first()
        if exists is None:
            return bib_number
