FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# ── Development ───────────────────────────────────────
FROM deps AS dev
COPY . .
EXPOSE 3000 24678
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ── Build ─────────────────────────────────────────────
FROM deps AS build
COPY . .
RUN npm run build

# ── Production ────────────────────────────────────────
FROM node:20-alpine AS prod
WORKDIR /app
COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules
EXPOSE 3000
CMD ["node", "build"]
