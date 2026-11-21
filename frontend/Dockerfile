# syntax=docker/dockerfile:1

# ---------- base: Node and pnpm ----------
FROM node:24.22.3-trixie-slim AS base

ENV NEXT_TELEMETRY_DISABLED=1 \
    CI=true

RUN npm install --global pnpm@12.21.0 && npm cache clean --force

WORKDIR /app

# ---------- dev: source is bind-mounted, hot reload ----------
FROM base AS dev

# node_modules and .next are named volumes in compose.yaml. Creating them here,
# owned by the non-root user, gives the volumes the right owner on first use.
RUN mkdir -p /app/node_modules /app/.next && chown -R node:node /app

USER node
COPY --chown=node:node package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

EXPOSE 3000
# The install at start is quick when nothing changed, and brings the
# node_modules volume up to date after package.json changes.
CMD ["sh", "-c", "pnpm install --frozen-lockfile && exec pnpm exec next dev --hostname 0.0.0.0 --port 3000"]

# ---------- deps: dependencies for the production build ----------
FROM base AS deps

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# ---------- builder: next build (standalone output) ----------
FROM base AS builder

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

# ---------- prod: only the built server, non-root ----------
FROM node:24.22.3-trixie-slim AS prod

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

WORKDIR /app

COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public

USER node
EXPOSE 3000
CMD ["node", "server.js"]
