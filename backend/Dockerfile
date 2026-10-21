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
# A MIGRÁCIÓ ÚJRAPRÓBÁLKOZIK: deploykor a RÉGI konténer még kiszolgál, és ha
# épp hosszú munkát végez az érintett táblán (pl. az automatikus számla-
# érkeztetés), a DDL a 30 mp-es lock_timeout-on (lásd alembic/env.py) elhasal
# - egyetlen ilyen ütközés ne buktassa el a deployt, csak ha tartósan nem
# jutunk zárhoz. A seed_detail_tabs díszítő, idempotens lépés: a hibája nem
# állíthatja meg az indulást. Az exec-kel az uvicorn lesz a PID 1 (rendes
# jelkezelés leállításkor).
CMD ["sh", "-c", "n=0; until alembic upgrade head; do n=$((n+1)); if [ $n -ge 5 ]; then echo 'A migráció 5 próbálkozás után sem futott le - a deploy leáll.'; exit 1; fi; echo \"Migráció újrapróbálása ($n/5) 8 mp múlva...\"; sleep 8; done; python scripts/seed_detail_tabs.py || echo 'seed_detail_tabs hibázott - az indulást nem állítja meg'; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
