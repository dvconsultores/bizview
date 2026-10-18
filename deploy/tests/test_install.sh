#!/usr/bin/env bash
# Checks are passed as strings and evaluated later, so single quotes are intended.
# shellcheck disable=SC2016,SC2034
# Tests for deploy/install.sh (contracts/installer.md). No real Docker needed: a fake `docker`
# on PATH answers the prerequisite checks. With REAL_DOCKER=1 the generated compose file is also
# validated with the real `docker compose config`.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
INSTALL="$HERE/../install.sh"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
FAKEBIN="$WORK/bin"; mkdir -p "$FAKEBIN"
printf '#!/bin/sh\nexit 0\n' >"$FAKEBIN/docker"; chmod +x "$FAKEBIN/docker"
REAL_PATH=$PATH
export PATH="$FAKEBIN:$PATH"

pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }

run() { bash "$INSTALL" "$@" >"$WORK/out" 2>"$WORK/err" </dev/null; echo $?; }

BASE=(--yes --version 1.2.3 --image-prefix ghcr.io/acme/bizview
      --db-url 'postgresql://u:p$ss@db.example:5432/bizview' --admin-email Admin@Example.com)

# 1. unattended install
D="$WORK/i1"
code=$(run "${BASE[@]}" --dir "$D")
check "exit 0" '[[ $code == 0 ]]'
check "layout" '[[ -f $D/.env && -f $D/docker-compose.yml && -d $D/branding && -d $D/workspace ]]'
check "worker service" 'grep -q "^  worker:" "$D/docker-compose.yml" && grep -q "app.worker" "$D/docker-compose.yml"'
check "workspace mounted read-only" '[[ $(grep -c "./workspace:/workspace:ro" "$D/docker-compose.yml") == 2 ]]'
check "projects folder" '[[ -d "$D/projects" ]]'
check "projects mounted in backend only" '[[ $(grep -c "./projects:/app/data/projects" "$D/docker-compose.yml") == 1 ]]'
check "project size setting" 'grep -q "^PROJECT_MAX_MB=20" "$D/.env"'
check "timezone written" 'grep -q "^TIMEZONE='"'"'" "$D/.env"'
check ".env is 600" '[[ $(stat -c %a "$D/.env") == 600 ]]'
check "compose is 644" '[[ $(stat -c %a "$D/docker-compose.yml") == 644 ]]'
check "version pinned" 'grep -q "^BIZVIEW_VERSION='"'"'1.2.3'"'"'" "$D/.env"'
check "email lower-cased" 'grep -q "^SUPER_USER_EMAIL='"'"'admin@example.com'"'"'" "$D/.env"'
check "db url literal" 'grep -qF "DATABASE_URL_BI='"'"'postgresql://u:p\$ss@db.example:5432/bizview'"'"'" "$D/.env"'
pw=$(sed -n "s/^SUPER_USER_PASSWORD='\(.*\)'$/\1/p" "$D/.env")
check "generated password 20 chars" '[[ ${#pw} == 20 ]]'
check "password shown once" '[[ $(grep -c "$pw" "$WORK/out") == 1 ]]'
check "http site: cookie not secure" 'grep -q "^COOKIE_SECURE=false" "$D/.env"'
check "AI off by default" 'grep -q "^AI_PROVIDER=none" "$D/.env"'
check "email placeholders commented" 'grep -q "^# SMTP_HOST=" "$D/.env"'
check "share links placeholder commented" 'grep -q "^# SHARE_LINKS_ENABLED=false" "$D/.env"'
check "no active email/share links setting" '! grep -qE "^(SMTP_|EMAIL_ALLOWED_DOMAINS|SHARE_LINKS_ENABLED)" "$D/.env"'
check "unstamped source url commented" 'grep -q "^# SOURCE_URL=" "$D/.env"'
check "no placeholders left" '! grep -q "__[A-Z_]*__" "$D/.env" "$D/docker-compose.yml"'
key=$(sed -n "s/^BIZVIEW_SECRET_KEY='\(.*\)'$/\1/p" "$D/.env")
check "secret key generated (32 bytes)" '[[ $(printf %s "$key" | tr "_-" "/+" | base64 -d 2>/dev/null | wc -c) == 32 ]]'
check "unattended profile auto" 'grep -q "^SECURITY_PROFILE=auto" "$D/.env"'

# 2. existing installation without --force
code=$(run "${BASE[@]}" --dir "$D")
check "refuse overwrite exit 3" '[[ $code == 3 ]]'
check "password unchanged" 'grep -q "$pw" "$D/.env"'

# 3. --force overwrites settings, keeps branding
touch "$D/branding/logo.svg"
code=$(run "${BASE[@]}" --dir "$D" --force --admin-password 'Another-pass-99')
check "force exit 0" '[[ $code == 0 ]]'
check "password replaced" 'grep -q "Another-pass-99" "$D/.env"'
check "given password not printed" '! grep -q "Another-pass-99" "$WORK/out"'
check "branding kept" '[[ -f $D/branding/logo.svg ]]'

# 4. domain → HTTPS settings
D="$WORK/i4"
code=$(run "${BASE[@]}" --dir "$D" --site dashboard.acme.com)
check "domain exit 0" '[[ $code == 0 ]]'
check "domain cookie secure" 'grep -q "^COOKIE_SECURE=true" "$D/.env"'
check "domain ports" 'grep -q "^HTTP_PORT=80" "$D/.env" && grep -q "^HTTPS_PORT=443" "$D/.env"'
check "summary https url" 'grep -q "https://dashboard.acme.com" "$WORK/out"'

# 4b. explicit profiles
D="$WORK/i4b"
code=$(run "${BASE[@]}" --dir "$D" --security-profile private)
check "private profile written" '[[ $code == 0 ]] && grep -q "^SECURITY_PROFILE=private" "$D/.env"'
code=$(run "${BASE[@]}" --dir "$WORK/i4c" --security-profile internet)
check "internet without domain exit 2" '[[ $code == 2 && ! -e $WORK/i4c/.env ]]'
code=$(run "${BASE[@]}" --dir "$WORK/i4d" --security-profile INTERNET --site bi.acme.com)
check "internet with domain" '[[ $code == 0 ]] && grep -q "^SECURITY_PROFILE=internet" "$WORK/i4d/.env"'
code=$(run "${BASE[@]}" --dir "$WORK/i4e" --security-profile open)
check "invalid profile exit 2" '[[ $code == 2 ]]'
k1=$(grep "^BIZVIEW_SECRET_KEY" "$D/.env"); k2=$(grep "^BIZVIEW_SECRET_KEY" "$WORK/i4d/.env")
check "keys differ per installation" '[[ "$k1" != "$k2" ]]'

# 5. missing answer with --yes → 2, nothing written
D="$WORK/i5"
code=$(run --yes --version 1.2.3 --image-prefix ghcr.io/acme/bizview --dir "$D" --admin-email a@b.co)
check "missing db url exit 2" '[[ $code == 2 ]]'
check "nothing written" '[[ ! -e $D ]]'

# 6. invalid values → 2
for bad in "--db-url mysql://x" "--admin-email nope" "--site bad_site!" "--http-port 70000" \
           "--version one" "--admin-password short" "--admin-password xxadminxxyy"; do
  # shellcheck disable=SC2086
  code=$(run "${BASE[@]}" --dir "$WORK/bad" $bad)
  check "invalid ($bad) exit 2" '[[ $code == 2 ]]'
done
check "invalid never written" '[[ ! -e $WORK/bad/.env ]]'

# 7. docker unusable → 1, nothing written
mv "$FAKEBIN/docker" "$FAKEBIN/docker.ok"
printf '#!/bin/sh\nexit 127\n' >"$FAKEBIN/docker"; chmod +x "$FAKEBIN/docker"
code=$(run "${BASE[@]}" --dir "$WORK/i7")
check "docker unusable exit 1" '[[ $code == 1 ]]'
check "docker unusable nothing written" '[[ ! -e $WORK/i7 ]]'
mv "$FAKEBIN/docker.ok" "$FAKEBIN/docker"

# 8. --opt=value form and stamped defaults
S="$WORK/stamped.sh"
sed -e 's/__BIZVIEW_VERSION__/9.9.9/' -e 's#__IMAGE_PREFIX__#ghcr.io/acme/bizview#' \
    -e 's#__SOURCE_URL__#https://github.com/acme/bizview#' "$INSTALL" >"$S"
D="$WORK/i8"
bash "$S" --yes --dir="$D" --db-url=postgresql://u:p@h/db --admin-email=x@y.co >/dev/null 2>&1 </dev/null
check "stamped version used" 'grep -q "^BIZVIEW_VERSION='"'"'9.9.9'"'"'" "$D/.env"'
check "stamped source url" 'grep -q "^SOURCE_URL='"'"'https://github.com/acme/bizview'"'"'" "$D/.env"'

# 9. the generated compose file is valid for the real Docker Compose
if [[ ${REAL_DOCKER:-0} == 1 ]]; then
  check "compose config valid" '(cd "$WORK/i4" && PATH=$REAL_PATH docker compose config -q)'
  check "compose images" '(cd "$WORK/i4" && PATH=$REAL_PATH docker compose config --images | sort | tr "\n" " ") | grep -q "ghcr.io/acme/bizview-backend:1.2.3 ghcr.io/acme/bizview-web:1.2.3"'
fi

echo "installer tests: $pass passed, $fail failed"
[[ $fail == 0 ]]
