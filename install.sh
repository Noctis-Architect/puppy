#!/usr/bin/env bash
# نصب کامل Message Guard (Puppy) — ربات شخصی خودمیزبان
# https://github.com/Noctis-Architect/puppy
set -euo pipefail

REPO_URL="https://github.com/Noctis-Architect/puppy.git"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}▸${NC} $*"; }
ok()    { echo -e "${GREEN}✔${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
fail()  { echo -e "${RED}✖${NC} $*"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       Message Guard — نصب ربات شخصی         ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""
warn "این ربات شخصی است — فقط روی سرور خودتان نصب کنید."
warn "هرگز اطلاعات کاربران را در سرور دیگران وارد نکنید."
echo ""

# --- پیش‌نیازها ---
info "بررسی پیش‌نیازها..."

command -v python3 >/dev/null 2>&1 || fail "python3 نصب نیست."
PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
info "Python $PYTHON_VERSION"

if ! python3 -c 'import venv' 2>/dev/null; then
    fail "ماژول venv موجود نیست. نصب کنید: sudo apt install python3-venv"
fi

# --- پوشه‌ها ---
mkdir -p data session logs
ok "پوشه‌های data/ و session/ ایجاد شدند"

# --- محیط مجازی ---
VENV_DIR="$SCRIPT_DIR/venv"
if [[ ! -f "$VENV_DIR/bin/python" ]]; then
    info "ساخت محیط مجازی Python..."
    python3 -m venv "$VENV_DIR"
    ok "venv ساخته شد"
else
    ok "venv از قبل موجود است"
fi

info "نصب وابستگی‌ها..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r requirements.txt -q
ok "پکیج‌ها نصب شدند"

# --- تنظیمات ---
CONFIG_FILE="$SCRIPT_DIR/config.json"
EXAMPLE_FILE="$SCRIPT_DIR/config.example.json"

if [[ ! -f "$CONFIG_FILE" ]]; then
    if [[ -f "$EXAMPLE_FILE" ]]; then
        cp "$EXAMPLE_FILE" "$CONFIG_FILE"
        ok "config.json از نمونه کپی شد"
    else
        fail "config.example.json یافت نشد"
    fi
    echo ""
    info "تنظیم config.json — api_id و api_hash از قبل در نمونه تنظیم شده‌اند."
    info "مقادیر زیر را از BotFather و @userinfobot بگیرید:"
    echo ""

    read -rp "  bot_token: " BOT_TOKEN
    read -rp "  super_admin_id (تلگرام ID شما): " SUPER_ADMIN

    python3 - "$CONFIG_FILE" "$BOT_TOKEN" "$SUPER_ADMIN" <<'PY'
import json, sys
path, bot_token, super_admin = sys.argv[1:4]
with open(path, encoding="utf-8") as f:
    cfg = json.load(f)
cfg["bot_token"] = bot_token.strip()
cfg["super_admin_id"] = int(super_admin)
with open(path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY
    ok "config.json ذخیره شد"
else
    ok "config.json از قبل موجود است (دست نخورده)"
fi

# --- تست اتصال پیکربندی ---
info "بررسی config.json..."
"$VENV_DIR/bin/python" -c "from app.config import AppConfig; AppConfig.load()" \
    || fail "config.json نامعتبر است — api_id، api_hash و bot_token را بررسی کنید."
ok "پیکربندی معتبر است"

# --- دیتابیس ---
info "راه‌اندازی دیتابیس..."
"$VENV_DIR/bin/python" -c "
import asyncio
from app.config import AppConfig
from app.db.session import init_db
asyncio.run(init_db(AppConfig.load()))
print('DB ready')
"
ok "دیتابیس آماده است"

echo ""
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  نصب با موفقیت انجام شد!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo ""
echo "  اجرای دستی:"
echo "    $VENV_DIR/bin/python main.py run"
echo ""
echo "  نصب سرویس systemd (نیاز به sudo):"
echo "    sudo bash install-service.sh"
echo ""
echo "  دستورات مفید:"
echo "    python main.py list-users"
echo "    python main.py add-user"
echo ""
echo "  ریپو: $REPO_URL"
echo ""
warn "فایل‌های حساس (config.json، session/، data/) را commit نکنید."
echo ""

read -rp "آیا می‌خواهید سرویس systemd نصب شود؟ [y/N] " INSTALL_SERVICE
if [[ "${INSTALL_SERVICE,,}" == "y" || "${INSTALL_SERVICE,,}" == "yes" ]]; then
    if [[ $EUID -eq 0 ]]; then
        bash "$SCRIPT_DIR/install-service.sh"
    else
        sudo bash "$SCRIPT_DIR/install-service.sh"
    fi
fi
