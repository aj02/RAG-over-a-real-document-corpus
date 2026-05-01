# syntax=docker/dockerfile:1.7

# ---------- deps ----------
FROM node:22-slim AS deps
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml* ./
# pnpm-lock.yaml is generated on first install; if it isn't committed yet,
# fall back to a non-frozen install so the image still builds.
RUN pnpm install --frozen-lockfile 2>/dev/null \
    || pnpm install --no-frozen-lockfile

# ---------- builder ----------
FROM node:22-slim AS builder
WORKDIR /app
RUN corepack enable
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_OUTPUT_STANDALONE=true
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* values are baked into the client bundle at build time. We
# default to localhost:8000; override at build with --build-arg if needed.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN pnpm build

# ---------- runtime ----------
FROM node:22-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN groupadd --system --gid 1001 nodejs \
    && useradd --system --uid 1001 --gid nodejs nextjs

# Standalone output bundles only what the runtime needs (server.js + minimal
# node_modules). public/ and the prerendered .next/static go alongside.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

# A bare GET on / is enough — Next.js renders 200 for valid app-router pages.
HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=20s \
    CMD node -e "require('http').get('http://127.0.0.1:3000/', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["node", "server.js"]
