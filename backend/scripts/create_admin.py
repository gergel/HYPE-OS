"""Első admin felhasználó létrehozása - a /api/v1/crew végpont admin jogot kér,
tehát az első usert közvetlenül a DB-n keresztül kell felvenni.

Használat: .venv/bin/python scripts/create_admin.py <email> <jelszo> <teljes_nev>
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.employee import Employee, EmployeeType, SystemRole


def create_admin(email: str, password: str, full_name: str) -> None:
    db = SessionLocal()
    try:
        existing = db.query(Employee).filter(Employee.email == email).first()
        if existing:
            print(f"Már létezik: {email}")
            return
        admin = Employee(
            full_name=full_name,
            tipus=EmployeeType.BELSOS,
            email=email,
            role=SystemRole.ADMIN,
            hashed_password=hash_password(password),
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"Admin létrehozva: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Használat: python scripts/create_admin.py <email> <jelszo> <teljes_nev>")
        sys.exit(1)
    create_admin(sys.argv[1], sys.argv[2], sys.argv[3])
