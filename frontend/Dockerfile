FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS builder
WORKDIR /app
# A NEXT_PUBLIC_* változók build-time-ban épülnek be a JS bundle-be (next build),
# nem futásidőben olvasódnak - Railway a Variables-t csak akkor adja át build
# arg-ként, ha a Dockerfile explicit ARG-ként deklarálja. Enélkül a build mindig
# a lib/api.ts-beli "http://localhost:8000" fallback-re esik vissza, függetlenül
# attól, hogy a Railway service Variables fülén mi van beállítva.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

# Railway a saját maga választotta (nem feltétlenül 3000) portot a PORT env
# var-ban adja át futásidőben, és arra irányítja a bejövő forgalmat - a "next
# start" ezt csak akkor veszi figyelembe, ha explicit átadjuk neki, különben
# mindig a 3000-es portra bindel és Railway nem éri el az appot.
EXPOSE 8080
CMD ["sh", "-c", "npm start -- -p ${PORT:-8080}"]
