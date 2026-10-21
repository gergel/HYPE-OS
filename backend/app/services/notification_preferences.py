"""Preferences belong to an authenticated person, not to a phone."""
from app.models.push import NotificationPreference

KINDS = {
    "mention": "Megjelölések",
    "assignment": "Rám osztott feladatok",
    "call_sheet": "Új diszpók",
    "comment": "Hozzászólások",
    "bejovo_szamla": "Bejövő számlák",
    "kotelezettseg": "Kötelezettségek és határidők",
    "anyagbekeres_leadas": "Anyagleadások",
    "vagoi_jatek_gyoztes": "Vágói játék eredménye",
    "vagoi_jatek_nyeremeny": "Vágói játék nyereménye",
    "lara_kerdes": "Lara kérdései",
    "lara_osszesito": "Lara napi összesítője",
    "lara_feladat": "Lara javaslatai (ellenőrzés, jóváhagyás)",
}

def enabled(db, employee_id, kind):
    # Unknown future events stay in the inbox but do not opt people into push.
    if kind not in KINDS:
        return False
    preference = db.get(NotificationPreference, (employee_id, kind))
    return preference is None or preference.enabled
