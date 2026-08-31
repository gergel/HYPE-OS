FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Railway (és a legtöbb PaaS) egy $PORT env var-ral mondja meg, melyik porton várja a
# kapcsolatot - ha ezt figyelmen kívül hagynánk és mindig 8000-re kötnénk, a platform
# proxyja 502-t adna, mert nem azon a porton figyelünk, amit ő elvár. Lokálisan/
# docker-compose-ban nincs PORT env var, ott az 8000-es alapértelmezés marad érvényben.
# TÖBB worker fut (WEB_CONCURRENCY env-vel hangolható): egyetlen processznél
# egy CPU-igényes kérés (pl. a diszpó-tábla sheet-szinkronja, egy nagy export)
# a GIL miatt az ÖSSZES többi kérést belassította - percekig töltött minden
# oldal mindenkinek. Két workernél a másik processz közben zavartalanul
# kiszolgál.
CMD ["sh", "-c", "alembic upgrade head && python scripts/seed_detail_tabs.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
