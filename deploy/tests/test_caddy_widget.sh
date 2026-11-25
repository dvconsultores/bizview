#!/usr/bin/env bash
# Feature 065: a widget's framed document may be framed by that widget's own sites and by nothing
# else, and every other route keeps refusing framing. Runs the edge (caddy:2-alpine with this
# repository's Caddyfile) in front of a stub "backend" that answers the frame decision the way
# app/api/widgets.py does. Needs Docker; touches no database.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
NET=bizview-widget-$$
WORK=$(mktemp -d)
cleanup() {
  docker rm -f "$NET-backend" "$NET-web" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "ok: $1"; else fail=$((fail+1)); echo "FAIL: $1"; fi; }

WIDGET_CSP="default-src 'self'; frame-ancestors https://www.cliente.com"
SITE_CSP="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
NONE_CSP="default-src 'self'; frame-ancestors 'none'"

# What the real image's entrypoint writes (deploy/caddy/entrypoint.sh); empty is enough here.
: > "$WORK/tls.snippet"
mkdir -p "$WORK/srv"
printf '<!doctype html><title>app</title>\n' > "$WORK/srv/index.html"

cat > "$WORK/stub.py" <<'PY'
"""Answers the frame decision the way app/api/widgets.py does."""
import http.server

WIDGET = "default-src 'self'; frame-ancestors https://www.cliente.com"
NONE = "default-src 'self'; frame-ancestors 'none'"


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        print(self.path, flush=True)
        if path.startswith("/api/widgets/frame/allowed"):
            self.send_response(200)
            self.send_header("Content-Security-Policy", WIDGET)
            self.send_header("X-Robots-Tag", "noindex, nofollow")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path.startswith("/api/widgets/frame/unknown"):
            self.send_response(200)
            self.send_header("Content-Security-Policy", NONE)
            self.send_header("X-Robots-Tag", "noindex, nofollow")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path.startswith("/api/widgets/frame/nopolicy"):
            self.send_response(200)   # no policy at all: the edge must fail closed
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
PY

docker network create "$NET" >/dev/null
docker run -d --name "$NET-backend" --network "$NET" --network-alias backend \
  -v "$WORK:/work:ro" python:3.12-alpine python /work/stub.py >/dev/null
docker run -d --name "$NET-web" --network "$NET" -e SITE_ADDRESS=:80 -p 127.0.0.1::80 \
  -v "$ROOT/deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v "$WORK/tls.snippet:/etc/caddy/tls.snippet:ro" \
  -v "$WORK/srv:/srv:ro" caddy:2-alpine >/dev/null

PORT=$(docker port "$NET-web" 80/tcp | head -1 | sed 's/.*://')
for _ in $(seq 1 40); do
  curl -sS -o /dev/null "http://127.0.0.1:$PORT/dashboard" 2>/dev/null && break
  sleep 1
done

headers() { curl -sS -D - -o /dev/null "$@" | tr -d '\r'; }

allowed=$(headers "http://127.0.0.1:$PORT/w/allowed")
# The widget's own list decides framing; the site-wide refusal is not on this document.
check "widget document keeps this widget's frame-ancestors" \
  'printf "%s" "$allowed" | grep -Fq "Content-Security-Policy: $WIDGET_CSP"'
check "widget document has no X-Frame-Options" \
  '! printf "%s" "$allowed" | grep -qi "^X-Frame-Options"'
check "widget document is never indexed" \
  'printf "%s" "$allowed" | grep -q "^X-Robots-Tag: noindex, nofollow"'
check "widget document is never stored" \
  'printf "%s" "$allowed" | grep -q "^Cache-Control: no-store"'

unknown=$(headers "http://127.0.0.1:$PORT/w/unknown")
check "unknown key is framed by nobody" \
  'printf "%s" "$unknown" | grep -Fq "Content-Security-Policy: $NONE_CSP"'

nopolicy=$(headers "http://127.0.0.1:$PORT/w/nopolicy")
check "a missing widget policy fails closed" \
  'printf "%s" "$nopolicy" | grep -Fq "$SITE_CSP"'

page=$(headers "http://127.0.0.1:$PORT/dashboard")
check "every other route still refuses framing" \
  'printf "%s" "$page" | grep -q "^X-Frame-Options: DENY"'
check "every other route keeps the site policy" \
  'printf "%s" "$page" | grep -Fq "Content-Security-Policy: $SITE_CSP"'

forged=$(headers -H "Content-Security-Policy: frame-ancestors *" "http://127.0.0.1:$PORT/w/allowed")
check "a client cannot forge the framing policy" \
  'printf "%s" "$forged" | grep -Fq "Content-Security-Policy: $WIDGET_CSP"'

curl -sS -o /dev/null "http://127.0.0.1:$PORT/w/allowed?period=mtd"
sleep 1
check "the backend is asked about the widget, query included" \
  'docker logs "$NET-backend" 2>&1 | grep -q "api/widgets/frame/allowed?period=mtd"'

echo "$pass passed, $fail failed"
[[ $fail == 0 ]]
