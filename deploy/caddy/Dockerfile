# Build context: repository root (see bizview.yml).
# Static assets are the same for every architecture: build them once, natively.
FROM --platform=$BUILDPLATFORM node:24-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build && npm run check:compat

FROM caddy:2-alpine
ARG BIZVIEW_VERSION=dev
ARG BIZVIEW_SOURCE_URL=""
LABEL org.opencontainers.image.title="bizview-web" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.version="${BIZVIEW_VERSION}" \
      org.opencontainers.image.source="${BIZVIEW_SOURCE_URL}"
COPY deploy/caddy/Caddyfile /etc/caddy/Caddyfile
COPY deploy/caddy/entrypoint.sh /usr/bin/caddy-entrypoint.sh
COPY deploy/branding /branding
COPY --from=web /web/dist /srv
# Empty by default so `caddy validate` succeeds; the entrypoint rewrites it at container start.
RUN chmod 755 /usr/bin/caddy-entrypoint.sh \
 && : >/etc/caddy/tls.snippet \
 && caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
ENTRYPOINT ["/usr/bin/caddy-entrypoint.sh"]
