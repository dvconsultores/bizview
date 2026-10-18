#!/usr/bin/env bash
# FR-023: a client cannot forge its address through Caddy. Runs the web image in front of a stub
# "backend" that echoes the X-Forwarded-For it receives. Needs Docker; touches no database.
set -euo pipefail
IMAGE=${WEB_IMAGE:-bizview-web:test}
NET=bizview-xff-$$
cleanup() { docker rm -f "$NET-backend" "$NET-web" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker network create "$NET" >/dev/null
docker run -d --name "$NET-backend" --network "$NET" --network-alias backend python:3.12-alpine \
  python -c '
import http.server, json
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"xff": self.headers.get("X-Forwarded-For")}).encode()
        self.send_response(200); self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()' >/dev/null
docker run -d --name "$NET-web" --network "$NET" -e SITE_ADDRESS=:80 -p 127.0.0.1::80 "$IMAGE" >/dev/null
PORT=$(docker port "$NET-web" 80/tcp | head -1 | sed 's/.*://')
for _ in $(seq 1 30); do curl -fs "http://127.0.0.1:$PORT/api/health" >/dev/null && break; sleep 1; done

got=$(curl -fs -H "X-Forwarded-For: 203.0.113.9" "http://127.0.0.1:$PORT/api/whoami")
echo "backend received: $got"
if printf '%s' "$got" | grep -q "203.0.113.9"; then
  echo "FAIL: forged X-Forwarded-For reached the backend"; exit 1
fi
echo "OK: forged address ignored"
