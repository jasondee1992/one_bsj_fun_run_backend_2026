from app.core.config import settings
from app.db.session import engine
from app.models import Base, Sequence
from sqlalchemy.orm import Session


def init_db() -> None:
    sqlite_path = settings.sqlite_file_path
    if sqlite_path is not None and sqlite_path.parent != sqlite_path:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        sequence = db.query(Sequence).filter(Sequence.name == "bib_number").one_or_none()
        if sequence is None:
            db.add(Sequence(name="bib_number", next_value=1))
            db.commit()

