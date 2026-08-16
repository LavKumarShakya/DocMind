# Production self-hosted frontend image for DocMind.
#
# Multi-stage build: installs dependencies and runs a production `next build`
# in the builder stage, then the slim runtime stage only carries the compiled
# output and production dependencies so `npm start` can serve the app.
#
# NEXT_PUBLIC_API_URL is baked into the client bundle at build time (Next.js
# inlines NEXT_PUBLIC_* at build), so it must be passed as a build ARG here,
# not injected at runtime. Compose supplies it via `args:`.

# ── Stage 1: dependencies ───────────────────────────────────────────────
FROM node:22-slim AS deps
WORKDIR /app

COPY package.json package-lock.json ./
# Reproducible install from the lockfile.
RUN npm ci

# ── Stage 2: build ───────────────────────────────────────────────────────
FROM node:22-slim AS builder
WORKDIR /app

# Build-time only variable; required for the API base URL in the client bundle.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
# Build with the production Node environment so `next build` optimizes output.
ENV NODE_ENV=production

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Keep the generated types tidy and enforce typechecks during the build.
RUN npm run build

# ── Stage 3: runtime ─────────────────────────────────────────────────────
FROM node:22-slim AS runner
WORKDIR /app

ENV NODE_ENV=production

# Create a non-root user for the runtime.
RUN groupadd --system --gid 1001 nodejs \
    && useradd --system --uid 1001 --gid nodejs nextjs

# Only what `next start` needs: compiled output, production deps, config.
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/package-lock.json ./package-lock.json
COPY --from=builder /app/next.config.ts ./next.config.ts
COPY --from=builder /app/node_modules ./node_modules

# Set the non-root user to run the server.
USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME=0.0.0.0

CMD ["npm", "start"]
