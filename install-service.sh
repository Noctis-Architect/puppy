#!/usr/bin/env bash
# نصب سرویس systemd برای Message Guard (Puppy) — ربات شخصی خودمیزبان
# https://github.com/Noctis-Architect/puppy
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}▸${NC} $*"; }
ok()    { echo -e "${GREEN}✔${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
fail()  { echo -e "${RED}✖${NC} $*"; exit 1; }

if [[ $EUID -ne 0 ]]; then
    echo "این اسکریپت باید با sudo اجرا شود:"
    echo "  sudo bash install-service.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$SCRIPT_DIR"
VENV_DIR="$INSTALL_DIR/venv"
SERVICE_NAME="puppy"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
RUN_USER="${SUDO_USER:-$(logname 2>/dev/null || echo root)}"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     نصب سرویس systemd — Message Guard       ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# --- بررسی‌ها ---
info "بررسی پیش‌نیازها..."

[[ -f "$VENV_DIR/bin/python" ]] \
    || fail "venv یافت نشد. ابتدا: bash install.sh"

[[ -f "$INSTALL_DIR/config.json" ]] \
    || fail "config.json یافت نشد. ابتدا: bash install.sh"

[[ -f "$INSTALL_DIR/main.py" ]] \
    || fail "main.py یافت نشد در $INSTALL_DIR"

# اعتبارسنجی config
info "اعتبارسنجی config.json..."
sudo -u "$RUN_USER" "$VENV_DIR/bin/python" -c \
    "from app.config import AppConfig; AppConfig.load()" \
    || fail "config.json نامعتبر است"

# دیتابیس
info "اطمینان از دیتابیس..."
sudo -u "$RUN_USER" bash -c "cd '$INSTALL_DIR' && '$VENV_DIR/bin/python' -c \"
import asyncio
from app.config import AppConfig
from app.db.session import init_db
asyncio.run(init_db(AppConfig.load()))
\""

mkdir -p "$INSTALL_DIR/data" "$INSTALL_DIR/session" "$INSTALL_DIR/logs"
chown -R "${RUN_USER}:${RUN_USER}" "$INSTALL_DIR"

# توقف نمونه قبلی
info "توقف نمونه قبلی (در صورت وجود)..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
pkill -f "${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/main.py run" 2>/dev/null || true
sleep 1

# ساخت unit file
info "ساخت فایل سرویس systemd..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Message Guard — Personal Telegram message archive bot
Documentation=https://github.com/Noctis-Architect/puppy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_USER}
WorkingDirectory=${INSTALL_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV_DIR}/bin/python ${INSTALL_DIR}/main.py run
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=puppy

# امنیت
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=${INSTALL_DIR}/data ${INSTALL_DIR}/session ${INSTALL_DIR}/logs
ProtectHome=read-only

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
sleep 2

echo ""
if systemctl is-active --quiet "$SERVICE_NAME"; then
    ok "سرویس ${SERVICE_NAME} فعال شد."
    echo ""
    systemctl status "$SERVICE_NAME" --no-pager -l | head -15
    echo ""
    echo "  دستورات مدیریت:"
    echo "    sudo systemctl status  ${SERVICE_NAME}"
    echo "    sudo systemctl restart ${SERVICE_NAME}"
    echo "    sudo systemctl stop    ${SERVICE_NAME}"
    echo "    sudo journalctl -u ${SERVICE_NAME} -f"
else
    fail "سرویس بالا نیامد. لاگ:"
    journalctl -u "$SERVICE_NAME" -n 40 --no-pager
fi
