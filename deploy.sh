#!/usr/bin/env bash
#
# deploy.sh — build & publish this project's images to Docker Hub from THIS machine.
#
#   ./deploy.sh                  # build + push :latest and the VERSION tag
#   ./deploy.sh --tag 0.2.0      # publish other tags instead (repeatable)
#   ./deploy.sh --help
#
# Everything runs against the local Docker engine; the server runs the pushed images, no SSH needed.
# Docker Hub login uses DOCKER_USERNAME / DOCKER_PASSWORD from .env (password via
# --password-stdin — it never appears on a command line or in the output).
#
# The stack runs from bizview.yml (compose project "bizview") and needs two images: the backend
# application image — the `worker` service reuses exactly this same image with another command —
# and the web/edge image (Caddy + the built SPA).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
VERSION_FILE="$SCRIPT_DIR/VERSION"

usage() {
  cat <<'EOF'
Usage: deploy.sh [options]

Builds both images from this repository and pushes them to Docker Hub.

  --tag TAG        publish this tag instead of the default set ("latest" + VERSION);
                   repeat the option for several tags, e.g. --tag latest --tag 0.1.0
  --help, -h       show this help

Images (Docker Hub, prefix "bizview"):
  <HUB_USER>/bizview-backend   backend/Dockerfile  (also used by the worker service)
  <HUB_USER>/bizview-web       deploy/caddy/Dockerfile  (Caddy + built frontend)

Defaults: HUB_USER comes from DOCKER_USERNAME in .env, else "andresdom2004".
Exit codes: 0 ok, 1 missing prerequisite, 2 Docker Hub login failed, 3 build failed.
EOF
}

env_val() {  # value of KEY in .env, without comments or quotes; never prints secrets
  local line
  line="$(grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 || true)"
  [[ -z "$line" ]] && { echo ""; return; }
  echo "$line" | cut -d= -f2- | sed -e 's/[[:space:]]*#.*$//' -e 's/^[[:space:]]*//' \
      -e 's/[[:space:]]*$//' -e 's/^"//' -e 's/"$//'
}

TAGS=()
while [[ $# -gt 0 ]]; do
  case $1 in
    --tag)
      [[ -n ${2-} ]] || { echo "❌ --tag needs a value" >&2; exit 1; }
      TAGS+=("$2"); shift 2 ;;
    --tag=*) TAGS+=("${1#*=}"); shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; echo "❌ unknown option: $1" >&2; exit 1 ;;
  esac
done

[[ -s "$VERSION_FILE" ]] || { echo "❌ VERSION not found in $SCRIPT_DIR" >&2; exit 1; }
VERSION="$(tr -d '[:space:]' <"$VERSION_FILE")"
if [[ ${#TAGS[@]} -eq 0 ]]; then TAGS=("latest" "$VERSION"); fi

HUB_USER=""
HUB_PASS=""
SOURCE_URL=""
if [[ -f "$ENV_FILE" ]]; then
  HUB_USER="$(env_val DOCKER_USERNAME)"
  HUB_PASS="$(env_val DOCKER_PASSWORD)"
  SOURCE_URL="$(env_val SOURCE_URL)"
else
  echo "⚠️  no .env found — using an existing Docker Hub session and DOCKER_USERNAME default." >&2
fi
HUB_USER="${HUB_USER:-andresdom2004}"

BACKEND_IMAGE="$HUB_USER/bizview-backend"
WEB_IMAGE="$HUB_USER/bizview-web"

IMAGE_PREFIX="$(env_val BIZVIEW_IMAGE_PREFIX)"
PREFIX_USER="${IMAGE_PREFIX%%/*}"   # "andresdom2004" out of "andresdom2004/bizview"
if [[ -n "$IMAGE_PREFIX" && "$IMAGE_PREFIX" != "your-dockerhub-user" && "$PREFIX_USER" != "$HUB_USER" ]]; then
  echo "⚠️  BIZVIEW_IMAGE_PREFIX=$IMAGE_PREFIX differs from DOCKER_USERNAME=$HUB_USER:" >&2
  echo "   the stack pulls ${IMAGE_PREFIX}-{backend,web} on the server, but this run pushes <$HUB_USER>/bizview-*." >&2
fi

# ── Docker availability ──────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  echo "❌ docker is not installed." >&2
  echo "   Install once: https://docs.docker.com/engine/install/" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "❌ cannot reach the local Docker daemon." >&2
  echo "   Fix access with:" >&2
  echo "     sudo systemctl start docker      # start the daemon" >&2
  echo "     sudo usermod -aG docker \$USER    # grant your user access" >&2
  echo "     newgrp docker                     # apply the group in this shell" >&2
  echo "   Then re-run $0." >&2
  exit 1
fi

# ── Commit (the local build uses the working tree) ──────────────────────────
COMMIT="$(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
if [[ -n "$(git -C "$SCRIPT_DIR" status --porcelain 2>/dev/null || true)" ]]; then
  echo "⚠️  uncommitted changes exist and WILL be included (the local build uses the working tree)." >&2
fi

# ── Docker Hub login ─────────────────────────────────────────────────────────
if [[ -n "$HUB_PASS" ]]; then
  printf '%s' "$HUB_PASS" | docker login -u "$HUB_USER" --password-stdin >/dev/null 2>&1 \
    || { echo "❌ docker hub login failed for $HUB_USER (check DOCKER_USERNAME/DOCKER_PASSWORD in .env)" >&2; exit 2; }
  echo "🔐 docker hub login ok ($HUB_USER)"
else
  DOCKER_CFG="${DOCKER_CONFIG:-$HOME/.docker}/config.json"
  if ! grep -q '"auths"' "$DOCKER_CFG" 2>/dev/null; then
    echo "❌ not logged in to Docker Hub. Add DOCKER_USERNAME/DOCKER_PASSWORD to .env, or run  docker login ." >&2
    exit 2
  fi
  echo "🔐 using the existing docker hub session ($HUB_USER)"
fi

# ── Build & push ────────────────────────────────────────────────────────────
build_args=(--build-arg "BIZVIEW_VERSION=$VERSION")
[[ -n "$SOURCE_URL" ]] && build_args+=(--build-arg "BIZVIEW_SOURCE_URL=$SOURCE_URL")
label="org.opencontainers.image.revision=$COMMIT"

echo "🐳 building backend (commit $COMMIT)"
docker build --label "$label" "${build_args[@]}" -t "$BACKEND_IMAGE:$VERSION" \
  -f "$SCRIPT_DIR/backend/Dockerfile" "$SCRIPT_DIR" || { echo "❌ backend build failed — nothing pushed" >&2; exit 3; }

echo "🐳 building web (Caddy + SPA)"
docker build --label "$label" "${build_args[@]}" -t "$WEB_IMAGE:$VERSION" \
  -f "$SCRIPT_DIR/deploy/caddy/Dockerfile" "$SCRIPT_DIR" || { echo "❌ web build failed — nothing pushed" >&2; exit 3; }

echo "📤 pushing"
pushed=()
for tag in "${TAGS[@]}"; do
  docker tag "$BACKEND_IMAGE:$VERSION" "$BACKEND_IMAGE:$tag"
  docker tag "$WEB_IMAGE:$VERSION" "$WEB_IMAGE:$tag"
  docker push "$BACKEND_IMAGE:$tag" >/dev/null
  docker push "$WEB_IMAGE:$tag" >/dev/null
  pushed+=("$tag")
done

echo
echo "✅ pushed (version $VERSION, commit $COMMIT)"
for tag in "${pushed[@]}"; do
  echo "   $BACKEND_IMAGE:$tag   (backend and worker)"
  echo "   $WEB_IMAGE:$tag       (Caddy + SPA)"
done
echo
echo "On the server, in the folder that holds bizview.yml:"
echo "   docker compose -f bizview.yml pull"
echo "   docker compose -f bizview.yml up -d"
echo "(set BIZVIEW_IMAGE_PREFIX=$HUB_USER and BIZVIEW_VERSION to the tag you want to run;"
echo " Watchtower can pull these tags on its own.)"
for tag in "${pushed[@]}"; do
  if [[ $tag == latest ]]; then
    echo "or let Watchtower pull $BACKEND_IMAGE:latest and $WEB_IMAGE:latest on its own."
    break
  fi
done
