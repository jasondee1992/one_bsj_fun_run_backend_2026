from app.core.config import settings
from app.db.session import engine
from app.models import Base, Sequence
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


PAYMENT_SCHEMA_UPGRADES: dict[str, str] = {
    "payment_method": "ALTER TABLE payments ADD COLUMN payment_method VARCHAR(80)",
    "qr_code_url": "ALTER TABLE payments ADD COLUMN qr_code_url VARCHAR(1000)",
    "qr_code_payload": "ALTER TABLE payments ADD COLUMN qr_code_payload TEXT",
    "payment_url": "ALTER TABLE payments ADD COLUMN payment_url VARCHAR(1000)",
    "provider_response_raw": "ALTER TABLE payments ADD COLUMN provider_response_raw TEXT",
    "expires_at": "ALTER TABLE payments ADD COLUMN expires_at DATETIME",
    "paid_at": "ALTER TABLE payments ADD COLUMN paid_at DATETIME",
    "webhook_last_event": "ALTER TABLE payments ADD COLUMN webhook_last_event VARCHAR(160)",
    "webhook_last_event_at": "ALTER TABLE payments ADD COLUMN webhook_last_event_at DATETIME",
}


def _upgrade_sqlite_schema() -> None:
    if settings.sqlite_file_path is None:
        return

    inspector = inspect(engine)
    if "payments" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("payments")}
    missing_columns = [
        statement
        for column_name, statement in PAYMENT_SCHEMA_UPGRADES.items()
        if column_name not in existing_columns
    ]
    if not missing_columns:
        return

    with engine.begin() as connection:
        for statement in missing_columns:
            connection.execute(text(statement))


def init_db() -> None:
    sqlite_path = settings.sqlite_file_path
    if sqlite_path is not None and sqlite_path.parent != sqlite_path:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)
    _upgrade_sqlite_schema()

    with Session(engine) as db:
        sequence = db.query(Sequence).filter(Sequence.name == "bib_number").one_or_none()
        if sequence is None:
            db.add(Sequence(name="bib_number", next_value=1))
            db.commit()
