# HYPE OS - Frontend

Next.js 16 (App Router) + TypeScript + Tailwind CSS v4. Lásd a repó gyökerében lévő `README.md`-t a teljes architektúráért.

## Fejlesztés

```bash
npm install
cp .env.example .env.local
npm run dev
```

A `.env.local`-ban a `NEXT_PUBLIC_API_URL` mutasson a futó backend API-ra (alapértelmezetten `http://localhost:8000`).

## Struktúra

- `app/` - route-ok (App Router), egy mappa = egy oldal a `lib/nav.ts`-ben definiált IA szerint
- `components/` - megosztott UI elemek (Sidebar, TopBar, Card, StatCard, StatusBadge)
- `lib/api.ts` - a backend API hívásainak wrappere
- `lib/nav.ts` - a bal oldali navigáció forrása (`hype_os_termekspecifikacio.md` 2. fejezete alapján)
