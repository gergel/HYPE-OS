"""Optimistic preconditions for replaying a previously saved PATCH."""
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

PATCH_PREFIXES: set[str] = set()


def check_precondition(metadata, changes: dict, current: dict) -> bool:
    """True means the entire change is already applied (e.g. a lost response).

    Missing keys are rejected: a partial/list snapshot must not authorize writes
    to a field the client never received. No changes are applied in this helper.
    """
    if (not isinstance(metadata, dict) or metadata.get("version") != 1
            or not isinstance(metadata.get("expected"), dict)
            or set(metadata["expected"]) != set(changes) or not changes):
        raise HTTPException(status_code=422, detail="Érvénytelen offline mentési előfeltétel.")
    current = jsonable_encoder(current)
    expected = metadata["expected"]
    already_applied = True
    for field, desired in changes.items():
        if field not in current:
            raise HTTPException(status_code=409, detail="A mező offline változata nem ellenőrizhető. Töltsd be újra az adatlapot.")
        if current[field] != desired:
            already_applied = False
            if current[field] != expected[field]:
                raise HTTPException(status_code=409, detail="Ütközés: az adatlapot közben más is szerkesztette. A helyi változat megmaradt.")
    return already_applied
