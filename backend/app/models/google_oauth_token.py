from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class GoogleOAuthToken(TimestampMixin, Base):
    """Egy Google fiókhoz tartozó, ADATBÁZISBAN tárolt OAuth hitelesítés - így
    adminnak elég egyszer bejelentkeznie a Beállítások oldalon ("Csatlakozás
    Google fiókkal"), és onnantól a háttérszinkron a refresh token segítségével
    magától megújítja a hozzáférést; nem kell kézzel token/service account
    JSON-t bemásolnia környezeti változóba (lásd services/google_oauth.py).

    A `key` azonosítja, mire szól a hitelesítés (jelenleg csak "calendar") -
    így egy későbbi integráció (pl. külön Drive fiók) ugyanezt a táblát
    használhatja új sorral, séma-módosítás nélkül.

    A `pending_state` a folyamatban lévő OAuth bejelentkezés CSRF-védelme: a
    "Csatlakozás" gomb generál egy véletlen értéket, és a Google csak azzal
    együtt tud visszatérni a callback végpontra. Erre azért van szükség, mert
    a callbacket a BÖNGÉSZŐ hívja meg a Google átirányítása után, ahol nem
    támaszkodhatunk a szokásos Bearer-token alapú admin hitelesítésre."""

    __tablename__ = "google_oauth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    # A google-auth "authorized user" formátumú JSON (refresh_token, client_id,
    # client_secret, token, token_uri) - a háttérszinkron ebből épít hitelesítést.
    token_json: Mapped[str | None] = mapped_column(Text)
    # Csak megjelenítéshez: melyik Google fiókkal van összekötve (a felületen
    # ez mutatja adminnak, hogy a HELYES fiókkal jelentkezett-e be).
    account_email: Mapped[str | None] = mapped_column(String(255))
    pending_state: Mapped[str | None] = mapped_column(String(128))
    pending_state_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # MIKOR újult meg utoljára a hozzáférés, és mi volt az utolsó hiba. Ez a
    # kettő együtt mondja meg, ÉL-E még a kapcsolat: a token_json megléte
    # önmagában nem elég, mert egy visszavont vagy lejárt refresh token
    # ugyanúgy ott áll a sorban - csak épp nem működik. Enélkül a felület
    # "Csatlakozva" állapotot mutatott, miközben a szinkron napok óta állt.
    last_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
