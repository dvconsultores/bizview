#!/usr/bin/env bash
# Bizview AI Powered — installer for one customer installation.
# SPDX-License-Identifier: AGPL-3.0-or-later
#
#   sudo bash deploy/install.sh                       # interactive: asks for the missing answers
#   sudo bash deploy/install.sh --version X.Y.Z --image-prefix <registry/owner>/bizview \
#     --yes --db-url 'postgresql://…' --admin-email admin@example.com --start
#
# Creates an installation folder (settings and a compose file pinned to a version) that runs the
# published images. Contract: specs/003-distribution-ai/contracts/installer.md
set -euo pipefail

# This copy is unstamped (the __…__ placeholders are empty), so unattended runs need --version and
# --image-prefix. A copy with the placeholders filled in can be attached to a release by hand.
DEFAULT_VERSION="__BIZVIEW_VERSION__"
DEFAULT_IMAGE_PREFIX="__IMAGE_PREFIX__"
DEFAULT_SOURCE_URL="__SOURCE_URL__"

DIR="/opt/bizview"
DB_URL=""
ADMIN_EMAIL=""
ADMIN_PASSWORD=""
SITE=":80"
HTTP_PORT=""
HTTPS_PORT=""
PRODUCT_NAME="Bizview AI Powered"
ORG_NAME=""
VERSION=""
IMAGE_PREFIX=""
SECURITY_PROFILE=""
TIMEZONE=""
ASSUME_YES=0
FORCE=0
START=0
GENERATED_PASSWORD=0

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die()  { local code=$1; shift; printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit "$code"; }

usage() {
  cat <<'EOF'
Usage: install.sh [options]

  --dir DIR               installation folder (default /opt/bizview)
  --db-url URL            PostgreSQL URL of the BI database (postgresql://user:pass@host:5432/db)
  --admin-email EMAIL     super user email
  --admin-password PW     super user password (default: generated and shown once;
                          prefer that - passwords on the command line reach shell history)
  --site ADDRESS          ":80" for plain HTTP, or a domain for automatic HTTPS (default :80)
  --security-profile P    private (HTTP allowed) | internet (HTTPS required everywhere,
                          two-step sign-in for administrators) | auto (internet for a domain)
  --timezone TZ           time zone for schedules and report periods, e.g. America/Caracas
                          (default: this server's time zone, else UTC)
  --http-port N           published HTTP port (default 80)
  --https-port N          published HTTPS port (default 443)
  --product-name NAME     name shown to users (default "Bizview AI Powered")
  --org-name NAME         organisation name shown under the product name (default empty)
  --version X.Y.Z         product version to run
  --image-prefix PREFIX   images are <prefix>-backend and <prefix>-web;
                          Docker Hub by default, e.g. andresdom2004/bizview
  --yes                   never ask; fail when a required answer is missing
  --force                 overwrite an existing .env and bizview.yml
  --start                 start the installation and wait until it is healthy
  --help                  show this help

Exit codes: 0 ok, 1 missing prerequisite, 2 invalid/missing answer,
            3 existing installation (use --force), 4 start failed.
EOF
}

stamped() { [[ -n $1 && $1 != __*__ ]]; }

# --- arguments ------------------------------------------------------------------------------
arg="" value="" has_value=0
take() {  # value of the current option: "--opt=value" or the next argument
  if [[ $has_value == 1 ]]; then printf '%s' "$value"; return; fi
  [[ -n ${1-} ]] || die 2 "missing value for $arg"
  printf '%s' "$1"
}

while [[ $# -gt 0 ]]; do
  arg=$1
  if [[ $arg == --*=* ]]; then value=${arg#*=}; arg=${arg%%=*}; has_value=1; else has_value=0; fi
  case $arg in
    --dir)            DIR=$(take "${2-}") ;;
    --db-url)         DB_URL=$(take "${2-}") ;;
    --admin-email)    ADMIN_EMAIL=$(take "${2-}") ;;
    --admin-password) ADMIN_PASSWORD=$(take "${2-}") ;;
    --site)           SITE=$(take "${2-}") ;;
    --security-profile) SECURITY_PROFILE=$(take "${2-}") ;;
    --timezone)       TIMEZONE=$(take "${2-}") ;;
    --http-port)      HTTP_PORT=$(take "${2-}") ;;
    --https-port)     HTTPS_PORT=$(take "${2-}") ;;
    --product-name)   PRODUCT_NAME=$(take "${2-}") ;;
    --org-name)       ORG_NAME=$(take "${2-}") ;;
    --version)        VERSION=$(take "${2-}") ;;
    --image-prefix)   IMAGE_PREFIX=$(take "${2-}") ;;
    --yes|-y)         ASSUME_YES=1 ;;
    --force)          FORCE=1 ;;
    --start)          START=1 ;;
    --help|-h)        usage; exit 0 ;;
    *)                usage >&2; die 2 "unknown option: $arg" ;;
  esac
  if [[ $has_value == 1 || $arg == --yes || $arg == -y || $arg == --force || $arg == --start ]]
  then shift; else shift 2; fi
done

# --- prerequisites (before touching anything) --------------------------------------------------
command -v docker >/dev/null 2>&1 || die 1 "Docker is not installed: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || die 1 "Docker Compose v2 is not available ('docker compose')."

# --- answers ----------------------------------------------------------------------------------
ask() {  # ask VAR "question" [secret]
  local var=$1 question=$2 secret=${3-} answer=""
  [[ -n ${!var} ]] && return
  if [[ $ASSUME_YES == 1 ]] || ! { : </dev/tty; } 2>/dev/null; then
    die 2 "missing required answer: $question (pass it as an option)"
  fi
  if [[ -n $secret ]]; then
    read -r -s -p "$question: " answer </dev/tty; echo >/dev/tty
  else
    read -r -p "$question: " answer </dev/tty
  fi
  printf -v "$var" '%s' "$answer"
}

stamped "$DEFAULT_VERSION" && [[ -z $VERSION ]] && VERSION=$DEFAULT_VERSION
stamped "$DEFAULT_IMAGE_PREFIX" && [[ -z $IMAGE_PREFIX ]] && IMAGE_PREFIX=$DEFAULT_IMAGE_PREFIX
ask VERSION "Product version (e.g. 0.1.0)"
ask IMAGE_PREFIX "Image prefix (e.g. andresdom2004/bizview, the images deploy.sh pushes)"
ask DB_URL "BI database URL (postgresql://user:pass@host:5432/db)"
ask ADMIN_EMAIL "Super user email"

# --- validation -------------------------------------------------------------------------------
[[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$|^latest$ ]] \
  || die 2 "invalid --version '$VERSION' (expected X.Y.Z)"
[[ $IMAGE_PREFIX =~ ^[a-z0-9._/:-]+$ ]] || die 2 "invalid --image-prefix '$IMAGE_PREFIX'"
[[ $DB_URL =~ ^postgres(ql)?:// ]] || die 2 "the database URL must start with postgresql://"
[[ $ADMIN_EMAIL =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]] \
  || die 2 "invalid super user email '$ADMIN_EMAIL'"
ADMIN_EMAIL=$(printf '%s' "$ADMIN_EMAIL" | tr '[:upper:]' '[:lower:]')

if [[ -z $ADMIN_PASSWORD ]]; then
  ADMIN_PASSWORD=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20 || true)
  GENERATED_PASSWORD=1
fi
local_part=${ADMIN_EMAIL%%@*}
lower_pw=$(printf '%s' "$ADMIN_PASSWORD" | tr '[:upper:]' '[:lower:]')
(( ${#ADMIN_PASSWORD} >= 10 && ${#ADMIN_PASSWORD} <= 128 )) \
  || die 2 "the super user password must have 10 to 128 characters"
if (( ${#local_part} >= 3 )) && [[ $lower_pw == *"$local_part"* ]]; then
  die 2 "the super user password must not contain the email"
fi

if [[ $SITE == :* ]]; then
  [[ $SITE =~ ^:[0-9]+$ ]] || die 2 "invalid --site '$SITE'"
  COOKIE_SECURE=false; SCHEME=http
  ALLOWED_HOSTS=""
else
  [[ $SITE =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)+$ ]] \
    || die 2 "invalid --site '$SITE' (use a domain name or :80)"
  COOKIE_SECURE=true; SCHEME=https
  ALLOWED_HOSTS=$SITE
fi
# Security option (feature 004): private allows HTTP; internet requires HTTPS everywhere.
suggested_profile=private; [[ $SITE == :* ]] || suggested_profile=internet
if [[ -z $SECURITY_PROFILE ]]; then
  if [[ $ASSUME_YES == 1 ]] || ! { : </dev/tty; } 2>/dev/null; then
    SECURITY_PROFILE=auto
  else
    read -r -p "Security profile [private = HTTP allowed | internet = HTTPS required] ($suggested_profile): " \
      SECURITY_PROFILE </dev/tty
    SECURITY_PROFILE=${SECURITY_PROFILE:-$suggested_profile}
  fi
fi
SECURITY_PROFILE=$(printf '%s' "$SECURITY_PROFILE" | tr '[:upper:]' '[:lower:]')
case $SECURITY_PROFILE in
  private|auto) ;;
  internet) [[ $SITE != :* ]] || die 2 "the internet profile requires a domain with HTTPS (--site)" ;;
  *) die 2 "invalid --security-profile '$SECURITY_PROFILE' (private, internet, or auto)" ;;
esac
# The internet profile refuses to start while direct reports may read the BI database with the
# application's own credentials and no read-only role is configured (app/security/profile.py).
DIRECT_REPORTS=true
if [[ $SECURITY_PROFILE == internet || ( $SECURITY_PROFILE == auto && $SITE != :* ) ]]; then
  DIRECT_REPORTS=false
fi

if [[ -z $TIMEZONE ]]; then
  TIMEZONE=$(cat /etc/timezone 2>/dev/null || true)
  [[ -n $TIMEZONE ]] || TIMEZONE=$(readlink /etc/localtime 2>/dev/null | sed -n 's|.*/zoneinfo/||p')
  TIMEZONE=${TIMEZONE:-UTC}
fi
[[ $TIMEZONE =~ ^[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+)*$ ]] || die 2 "invalid --timezone '$TIMEZONE'"

HTTP_PORT=${HTTP_PORT:-80}
HTTPS_PORT=${HTTPS_PORT:-443}
for p in "$HTTP_PORT" "$HTTPS_PORT"; do
  if ! [[ $p =~ ^[0-9]+$ ]] || (( p < 1 || p > 65535 )); then die 2 "invalid port '$p'"; fi
done

# Values are written single-quoted (literal) in .env; these characters cannot be represented.
for v in "$DB_URL" "$ADMIN_PASSWORD" "$PRODUCT_NAME" "$ORG_NAME"; do
  [[ $v != *"'"* && $v != *$'\n'* ]] || die 2 "values cannot contain single quotes or new lines"
done

# --- existing installation ----------------------------------------------------------------------
if [[ -e $DIR/.env && $FORCE != 1 ]]; then
  die 3 "$DIR already contains an installation (.env). Use --force to overwrite its settings."
fi

# --- write the installation -------------------------------------------------------------------
mkdir -p "$DIR/projects" "$DIR/attachments" 2>/dev/null \
  || die 2 "cannot create $DIR (run with sudo or choose --dir)"
chmod 755 "$DIR"
# In-app data written by the containers, which run as uid 10001 ('app'): BI projects (feature 020,
# one folder per project) and the images attached to the assistant (feature 024).
chmod 0750 "$DIR/projects" "$DIR/attachments"
if [[ $(id -u) == 0 ]]; then
  chown 10001:10001 "$DIR/projects" "$DIR/attachments"
  PROJECTS_NOTE=""
else
  PROJECTS_NOTE="  Projects:    run: sudo chown -R 10001:10001 $DIR/projects $DIR/attachments"
fi

SECRET_KEY=$(head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '\n')

source_line="# SOURCE_URL=        # override the source-code link (default: baked into the image)"
stamped "$DEFAULT_SOURCE_URL" && source_line="SOURCE_URL='$DEFAULT_SOURCE_URL'"

old_umask=$(umask)
umask 077
cat >"$DIR/.env" <<EOF
# Bizview AI Powered — installation settings. Keep this file private (mode 600).
# Upgrade: change BIZVIEW_VERSION, then run: docker compose pull && docker compose up -d
BIZVIEW_VERSION='$VERSION'
BIZVIEW_IMAGE_PREFIX='$IMAGE_PREFIX'
# The compose file of this installation; lets `docker compose up -d` work without -f.
COMPOSE_FILE=bizview.yml

# Database (always external; the product's tables live in schema public)
DATABASE_URL_BI='$DB_URL'

# Super user: created on first start. Changing these later has no effect; see docs/INSTALL.md
SUPER_USER_EMAIL='$ADMIN_EMAIL'
SUPER_USER_PASSWORD='$ADMIN_PASSWORD'

# Branding: the logo ships inside the web image. Set LOGO_URL to a URL to use another one.
PRODUCT_NAME='$PRODUCT_NAME'
ORGANIZATION_NAME='$ORG_NAME'
LOGO_URL=

# Public address: ":80" for HTTP, or a domain for automatic HTTPS
SITE_ADDRESS='$SITE'
# The only Host names this installation answers; any other Host gets 421. Empty = no check.
CADDY_ALLOWED_HOSTS='$ALLOWED_HOSTS'
HTTP_PORT=$HTTP_PORT
HTTPS_PORT=$HTTPS_PORT
# Certificate source: auto (ACME) | internal (Caddy's CA) | file (a pair in CADDY_TLS_DIR).
# The last two need no free port; see docs/INSTALL.md.
CADDY_TLS=auto
# CADDY_TLS_DIR=./caddy-certs          # origin.pem + origin-key.pem for CADDY_TLS=file
COOKIE_SECURE=$COOKIE_SECURE
$source_line

# Security option: private (HTTP allowed) | internet (HTTPS required, two-step sign-in for
# administrators) | auto (internet when SITE_ADDRESS is a domain)
SECURITY_PROFILE=$SECURITY_PROFILE
# Key that encrypts stored credentials. BACK IT UP separately from database backups:
# without it, data-source credentials and two-step sign-in must be set up again.
BIZVIEW_SECRET_KEY='$SECRET_KEY'
# ADMIN_ALLOWED_NETWORKS=10.0.0.0/8      # optional: administration only from these networks
# SOURCES_ALLOW_PRIVATE_NETWORKS=true    # data sources may be on private networks
# LOGIN_RATE_LIMIT=20                    # failed sign-ins per address per window
# LOGIN_RATE_WINDOW_MINUTES=15
# TRUSTED_PROXIES=10.0.0.0/8            # only if a load balancer sits in front of this server
# Direct reports (feature 019): reports that read the BI database without an integration.
# The internet profile requires DIRECT_BI_ROLE (below) while this is true, so it stays off until
# a read-only role exists: create it, set DIRECT_BI_ROLE, then set this to true.
DIRECT_REPORTS_BI=$DIRECT_REPORTS
# DIRECT_BI_ROLE=                      # read-only role for built-in bi sessions; create it with:
#   CREATE ROLE bizview_direct NOLOGIN;
#   GRANT USAGE ON SCHEMA public TO bizview_direct;
#   GRANT SELECT ON public.<table> TO bizview_direct;  # repeat per allowed table in public
#   # never ON ALL TABLES / DEFAULT PRIVILEGES in public; never grant on product tables
#   # reporting or ds_* schema: GRANT USAGE, SELECT ON ALL TABLES, DEFAULT PRIVILEGES
#   GRANT bizview_direct TO <app user>;
#   NOTE: re-run the grants for a ds_* schema after the engine recreates it
#   (integration deleted or re-applied); a dedicated reporting schema is better.
#   Views/functions rules: see docs/INSTALL.md section 5.

# Vibe reporting: integrations and reports are declared in the workspace stored in the database
# and applied in Administración → Espacio de trabajo.
TIMEZONE='$TIMEZONE'

# BI projects (feature 020): ./projects is mounted read-write into the backend only.
PROJECT_MAX_MB=20

# Watchtower pulls a newer image of BIZVIEW_VERSION every N seconds; it only recreates the
# services of this installation. With a fixed version tag it waits until the tag changes.
WATCHTOWER_POLL_INTERVAL=300

# AI (optional, off by default). Providers: none | anthropic | openai_compatible
#   anthropic:          AI_API_KEY required; AI_MODEL defaults to claude-opus-5-5
#   openai_compatible:  AI_BASE_URL (e.g. http://ollama:11434/v1) and AI_MODEL required
AI_PROVIDER=none
AI_API_KEY=
AI_MODEL=
AI_BASE_URL=
AI_TIMEOUT_SECONDS=30
# Assistant agent limits (optional; defaults shown)
# AI_CHAT_MAX_ROUNDS=20
# AI_CHAT_BUDGET_STEP=100000
# AI_CHAT_BUDGET_MAX=2000000
# AI_CHAT_MAX_PREVIEWS=5
# AI_TOOL_TIMEOUT_SECONDS=20
# AI_CHAT_TIMEOUT_SECONDS=180
# AI_AGENT_DISCOVERY_LIMIT=15
# AI_CHAT_BUSY_STALE_SECONDS=900

# Email and shared links (optional, off by default). Email is on when SMTP_HOST and SMTP_FROM
#   are set; the worker service sends the mail. Test: docker compose run --rm backend python -m
#   app.cli mail-test ADDRESS
# SMTP_HOST=
#   587 = STARTTLS (default); 465 = SSL/TLS
# SMTP_PORT=587
#   starttls | ssl | none (none refused on the internet profile); empty = by port
# SMTP_SECURITY=
# SMTP_USER=
#   secret: never shown or logged; ASCII only
# SMTP_PASSWORD=
# SMTP_FROM=
#   sender display name; defaults to ORGANIZATION_NAME
# SMTP_FROM_NAME=
#   external recipient domains, comma-separated; empty = installation users only
# EMAIL_ALLOWED_DOMAINS=
#   read-only dashboard links that expire after 1-90 days (Compartir)
# SHARE_LINKS_ENABLED=false

DOCS_ENABLED=false
LOG_LEVEL=INFO
EOF
chmod 600 "$DIR/.env"
umask "$old_umask"

cat >"$DIR/bizview.yml" <<'EOF'
# Bizview AI Powered — one customer installation. Generated by install.sh.
# All settings are in .env next to this file. Do not edit images here; change BIZVIEW_VERSION.
name: bizview
services:
  backend:
    container_name: bizview-backend
    image: ${BIZVIEW_IMAGE_PREFIX}-backend:${BIZVIEW_VERSION}
    labels:
      com.centurylinklabs.watchtower.enable: "true"
    env_file: .env
    restart: unless-stopped
    expose: ["8000"]
    environment:
      PROJECTS_DIR: /app/data/projects
    volumes:
      - ./projects:/app/data/projects
      - ./attachments:/app/data/attachments

  worker:
    container_name: bizview-worker
    image: ${BIZVIEW_IMAGE_PREFIX}-backend:${BIZVIEW_VERSION}
    labels:
      com.centurylinklabs.watchtower.enable: "true"
    command: ["python", "-m", "app.worker"]
    env_file: .env
    environment:
      ATTACHMENTS_DIR: /app/data/attachments
    restart: unless-stopped
    volumes:
      - ./attachments:/app/data/attachments
    healthcheck:
      disable: true
    depends_on:
      backend:
        condition: service_healthy

  web:
    container_name: bizview-web
    image: ${BIZVIEW_IMAGE_PREFIX}-web:${BIZVIEW_VERSION}
    labels:
      com.centurylinklabs.watchtower.enable: "true"
    environment:
      SITE_ADDRESS: ${SITE_ADDRESS}
      CADDY_ALLOWED_HOSTS: ${CADDY_ALLOWED_HOSTS:-}
      CADDY_TLS: ${CADDY_TLS:-auto}
      CADDY_TLS_CERT: ${CADDY_TLS_CERT:-/certs/origin.pem}
      CADDY_TLS_KEY: ${CADDY_TLS_KEY:-/certs/origin-key.pem}
      TRUSTED_PROXIES: ${TRUSTED_PROXIES:-127.0.0.1/32}
    ports:
      # LEFT of the colon is the host port (the only side that can collide with another stack);
      # RIGHT is inside the container, where Caddy always listens on 80 and 443.
      - "${HTTP_PORT}:80"
      - "${HTTPS_PORT}:443"
      # HTTP/3 (QUIC) uses the same number over UDP; delete this line if that port is taken.
      - "${HTTPS_PORT}:443/udp"
    volumes:
      - ${CADDY_TLS_DIR:-./caddy-certs}:/certs:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  # Pulls a new image when the tag in BIZVIEW_VERSION is republished, and recreates only the
  # labelled services above (never other stacks on a shared host). Remove it to upgrade by hand.
  watchtower:
    image: containrrr/watchtower:1.7.1
    container_name: bizview-watchtower
    restart: unless-stopped
    environment:
      WATCHTOWER_LABEL_ENABLE: "true"
      WATCHTOWER_CLEANUP: "true"
      WATCHTOWER_ROLLING_RESTART: "true"
      WATCHTOWER_POLL_INTERVAL: ${WATCHTOWER_POLL_INTERVAL:-300}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

volumes:
  caddy_data:
  caddy_config:
EOF
chmod 644 "$DIR/bizview.yml"

say "Installation written to $DIR (version $VERSION)"

# --- start ------------------------------------------------------------------------------------
if [[ $START == 1 ]]; then
  say "Starting (the first start migrates the database and creates the super user)…"
  (cd "$DIR" && docker compose up -d) || die 4 "docker compose up failed"
  status=""
  for _ in $(seq 1 60); do
    status=$(cd "$DIR" && docker compose ps backend --format '{{.Health}}' 2>/dev/null || true)
    [[ $status == healthy ]] && break
    sleep 3
  done
  if [[ $status != healthy ]]; then
    (cd "$DIR" && docker compose logs --tail 40 backend) >&2 || true
    die 4 "the backend did not become healthy (logs above)"
  fi
  say "Running."
fi

# --- summary ----------------------------------------------------------------------------------
if [[ $SITE == :* ]]; then
  port_suffix=""; [[ $HTTP_PORT != 80 ]] && port_suffix=":$HTTP_PORT"
  url="http://<this-server>$port_suffix"
else
  port_suffix=""; [[ $HTTPS_PORT != 443 ]] && port_suffix=":$HTTPS_PORT"
  url="$SCHEME://$SITE$port_suffix"
fi
cat <<EOF

  Bizview AI Powered — installation ready
  ----------------------------------------
  Folder:      $DIR
  Address:     $url
  Super user:  $ADMIN_EMAIL
  Security:    $SECURITY_PROFILE
  Time zone:   $TIMEZONE
  Projects:    $DIR/projects (one folder per BI project; back it up with the database)
EOF
if [[ -n $PROJECTS_NOTE ]]; then printf '%s\n' "$PROJECTS_NOTE"; fi
if [[ $GENERATED_PASSWORD == 1 ]]; then
  printf '  Password:    %s   (generated; shown only now — also stored in %s/.env)\n' \
    "$ADMIN_PASSWORD" "$DIR"
fi
cat <<EOF

  Start/stop:  cd $DIR && docker compose up -d   |   docker compose down
  Upgrade:     set BIZVIEW_VERSION in .env, then docker compose pull && docker compose up -d
  Branding/AI/email: edit $DIR/.env (see the comments), then docker compose up -d
  Secret key:  back up BIZVIEW_SECRET_KEY from $DIR/.env in a safe place (password manager)
EOF
[[ $START == 1 ]] || printf '\n  Not started yet: cd %s && docker compose up -d\n' "$DIR"
