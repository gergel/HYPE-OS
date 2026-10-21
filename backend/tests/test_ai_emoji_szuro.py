"""Az AI által írt leírásba/kommentbe emoji nem kerül (a felhasználó kérése,
2026-10): az AI Assistant minden írása (api_muvelet) emoji-szűrőn megy át.

Tranzakcióban fut a helyi adatbázison, és a végén VISSZAGÖRGETŐDIK; a belső
API-hívás le van cserélve (semmi nem íródik valódi rekordba)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.ai_beszelgetes import AiBeszelgetes, AiMuvelet
from app.models.employee import Employee, EmployeeType, SystemRole
from app.services.emoji_szuro import emoji_nelkul, emoji_nelkul_melyen


def test_emojik_kiesnek_a_szoveg_es_a_formazas_marad():
    assert emoji_nelkul("⏱️ SÜRGŐS - 2 ÓRÁN BELÜL SZÜKSÉGES!") == "SÜRGŐS - 2 ÓRÁN BELÜL SZÜKSÉGES!"
    assert emoji_nelkul("### 🔤 KÜLÖN KIEMELT STÍLUSELEM") == "### KÜLÖN KIEMELT STÍLUSELEM"
    assert emoji_nelkul("  - ✅ **Hossz:** ~60 mp") == "  - **Hossz:** ~60 mp"
    assert emoji_nelkul("1️⃣ első lépés") == "1 első lépés"
    # Ékezet, tipográfia, link, markdown érintetlen; emoji nélküli sor változatlan.
    sima = "Árvíztűrő – „idézet” → © https://hypeclient.com/p/x  két szóköz"
    assert emoji_nelkul(sima) == sima
    assert emoji_nelkul("a 🚚 b\n\n---\nc") == "a b\n\n---\nc"
    assert emoji_nelkul_melyen({"body": "Kész 🎉", "n": 3, "l": ["👍 ok"]}) == {"body": "Kész", "n": 3, "l": ["ok"]}


@pytest.fixture
def db():
    with engine.connect() as conn:
        tx = conn.begin()
        sess = Session(bind=conn, join_transaction_mode="create_savepoint")
        try:
            yield sess
        finally:
            sess.close()
            tx.rollback()


def test_ai_iras_emoji_nelkul_megy_es_naplozodik(db, monkeypatch):
    from app.services import ai_eszkozok

    user = Employee(full_name="AI Emoji Teszt (demó)", tipus=EmployeeType.BELSOS, email="ai-emoji-demo@example.test",
                    role=SystemRole.ADMIN, is_active=True)
    db.add(user)
    db.flush()
    b = AiBeszelgetes(employee_id=user.id)
    db.add(b)
    db.flush()
    db.commit = db.flush
    elkuldott = {}

    def belso(_user, method, path, json_body=None, **kw):
        elkuldott.update({"method": method, "path": path, "body": json_body})
        return 201, {"id": 1}

    monkeypatch.setattr(ai_eszkozok, "_belso_hivas", belso)
    e = ai_eszkozok.api_muvelet(
        db, user, b.id, method="POST", path="/api/v1/deliverables/1/comments",
        body={"body": "⏱️ SÜRGŐS\n\n### 🔤 BRÍF:\n- **Téma:** fuvarozás 🚚"},
        idempotencia_kulcs="komment-deliverable-1-1", osszefoglalo="komment",
    )
    assert e["status"] == 201
    vart = "SÜRGŐS\n\n### BRÍF:\n- **Téma:** fuvarozás"
    assert elkuldott["body"] == {"body": vart}
    assert db.query(AiMuvelet).filter_by(beszelgetes_id=b.id).one().keres == {"body": vart}
