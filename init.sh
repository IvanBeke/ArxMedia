#!/bin/bash
# init.sh - ArxMedia harness verification

set -e

cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo "=== ArxMedia Harness Init ==="
echo

# 1. Check .env has TMDB_API_KEY
echo -n "Checking TMDB_API_KEY... "
if [ -f .env ] && grep -q "TMDB_API_KEY=" .env && grep -v "^#" .env | grep -q "TMDB_API_KEY=[^ ]"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARNING${NC} — TMDB_API_KEY not set in .env. TMDB features will fail."
fi

# 1b. Check .env has FERNET_KEY
echo -n "Checking FERNET_KEY... "
if [ -f .env ] && grep -v "^#" .env | grep -q "FERNET_KEY=[^ ]"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}WARNING${NC} — FERNET_KEY not set in .env. Using SECRET_KEY-derived fallback key."
fi

# 2. Check Docker Compose services
echo -n "Checking Docker Compose services... "
if docker compose ps --format json 2>/dev/null | grep -q '"Service"'; then
    PS_JSON=$(docker compose ps --format json 2>/dev/null || true)
    TOTAL=$(printf '%s\n' "$PS_JSON" | grep -c '"Service"' || true)
    RUNNING=$(printf '%s\n' "$PS_JSON" | grep -c '"State":"running"' || true)
    TOTAL=${TOTAL:-0}
    RUNNING=${RUNNING:-0}
    if [ "$RUNNING" -ge 1 ]; then
        echo -e "${GREEN}OK${NC} ($RUNNING/$TOTAL services up)"
    else
        echo -e "${RED}FAIL${NC} — 0 services running. Run: docker compose up --build -d"
        exit 1
    fi
else
    echo -e "${YELLOW}WARNING${NC} — Docker Compose not running or not configured. Run: docker compose up --build -d"
fi

# 3. Check migrations applied
echo -n "Checking Django migrations... "
if command -v docker &>/dev/null && docker compose ps app &>/dev/null 2>&1; then
    UNAPPLIED=$(docker compose exec -T app python manage.py showmigrations 2>/dev/null | grep -c " \[ \]" || true)
    UNAPPLIED=${UNAPPLIED:-0}
    if [ "$UNAPPLIED" -eq 0 ]; then
        echo -e "${GREEN}OK${NC} (all applied)"
    else
        echo -e "${RED}FAIL${NC} — $UNAPPLIED unapplied migrations. Run: docker compose exec app python manage.py migrate"
        exit 1
    fi
else
    echo -e "${YELLOW}SKIP${NC} (app not running)"
fi

# 4. Check no hardcoded secrets in src/
echo -n "Checking for hardcoded secrets... "
if grep -rE "SECRET_KEY\s*=\s*['\"][^'\"]+|TMDB_API_KEY\s*=\s*['\"][^'\"]+|DATABASE_URL\s*=\s*['\"][^'\"]+|REDIS_URL\s*=\s*['\"][^'\"]+" src/ --include="*.py" \
    | grep -v "os.environ\|settings\." \
    | grep -v "^#" \
    | grep -v "_example\|placeholder" >/dev/null 2>&1; then
    echo -e "${RED}FAIL${NC} — Possible hardcoded secrets found"
    exit 1
fi
echo -e "${GREEN}OK${NC}"

# 5. Check init script is executable
echo -n "Checking init.sh permissions... "
if [ ! -x "$0" ]; then
    chmod +x "$0"
fi
echo -e "${GREEN}OK${NC}"

echo
echo -e "${GREEN}=== All checks passed ===${NC}"
echo "Run your task-focused workflow from repo root using Docker commands."
