#!/usr/bin/env bash
# Message Guard (Puppy) — نصب / به‌روزرسانی مستقیم از GitHub
# https://github.com/Noctis-Architect/puppy
#
# نصب:        curl -fsSL .../install.sh | bash
# به‌روزرسانی: curl -fsSL .../install.sh | bash -s -- -u
set -euo pipefail

GITHUB_REPO="Noctis-Architect/puppy"
REPO_URL="https://github.com/${GITHUB_REPO}.git"
DEFAULT_BRANCH="main"
ARCHIVE_URL="https://github.com/${GITHUB_REPO}/archive/refs/heads/${DEFAULT_BRANCH}.tar.gz"
RAW_INSTALL_URL="https://raw.githubusercontent.com/${GITHUB_REPO}/${DEFAULT_BRANCH}/install.sh"

MARKER_DIR="${HOME}/.puppy"
MARKER_FILE="${MARKER_DIR}/install_dir"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}▸${NC} $*"; }
ok()    { echo -e "${GREEN}✔${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC} $*"; }
fail()  { echo -e "${RED}✖${NC} $*"; exit 1; }

UPDATE_MODE=0
SKIP_SERVICE_PROMPT=0
FORCE_FRESH=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --update|-u) UPDATE_MODE=1; shift ;;
        --no-service) SKIP_SERVICE_PROMPT=1; shift ;;
        --fresh) FORCE_FRESH=1; UPDATE_MODE=0; shift ;;
        --dir)
            [[ $# -ge 2 ]] || fail "بعد از --dir مسیر لازم است"
            PUPPY_INSTALL_DIR="$2"
            shift 2
            ;;
        --help|-h)
            cat <<HELP
نصب:        curl -fsSL ${RAW_INSTALL_URL} | bash
به‌روزرسانی: curl -fsSL ${RAW_INSTALL_URL} | bash -s -- -u
نصب مجدد:   curl -fsSL ${RAW_INSTALL_URL} | bash -s -- --fresh

گزینه‌ها: -u آپدیت | --fresh نصب/ترمیم | --dir PATH | --no-service
HELP
            exit 0
            ;;
        *) fail "گزینه ناشناخته: $1" ;;
    esac
done

has_install_at() {
    [[ -f "${1}/main.py" && -f "${1}/requirements.txt" ]]
}

resolve_install_dir() {
    if [[ -n "${PUPPY_INSTALL_DIR:-}" ]]; then
        echo "$PUPPY_INSTALL_DIR"
        return
    fi

    if [[ -f "$MARKER_FILE" ]]; then
        local saved
        saved="$(tr -d '\n' < "$MARKER_FILE")"
        if [[ -n "$saved" ]] && has_install_at "$saved"; then
            echo "$saved"
            return
        fi
    fi

    local script_path="${BASH_SOURCE[0]:-$0}"
    if [[ -f "$script_path" ]] \
        && [[ "$script_path" != /dev/fd/* ]] \
        && [[ "$script_path" != /proc/* ]]; then
        local script_dir
        script_dir="$(cd "$(dirname "$script_path")" && pwd)"
        if has_install_at "$script_dir"; then
            echo "$script_dir"
            return
        fi
    fi

    if has_install_at "$(pwd)"; then
        echo "$(pwd)"
        return
    fi

    echo "${HOME}/puppy"
}

INSTALL_DIR="$(resolve_install_dir)"
CONFIG_FILE="${INSTALL_DIR}/config.json"
EXAMPLE_FILE="${INSTALL_DIR}/config.example.json"
VENV_DIR="${INSTALL_DIR}/venv"

save_install_dir() {
    mkdir -p "$MARKER_DIR"
    printf '%s\n' "$INSTALL_DIR" > "$MARKER_FILE"
}

refresh_local_install_script() {
    command -v curl >/dev/null 2>&1 || return
    if curl -fsSL "$RAW_INSTALL_URL" -o "${INSTALL_DIR}/install.sh" 2>/dev/null; then
        chmod +x "${INSTALL_DIR}/install.sh"
    fi
}

# تشخیص حالت: فقط وجود main.py = نصب شده (نه marker تنها)
if [[ "$FORCE_FRESH" -eq 1 ]]; then
    INSTALL_MODE="fresh"
elif [[ "$UPDATE_MODE" -eq 1 ]]; then
    if has_install_at "$INSTALL_DIR"; then
        INSTALL_MODE="update"
    else
        warn "نصب ناقص بود — در حال نصب/ترمیم..."
        INSTALL_MODE="fresh"
    fi
elif has_install_at "$INSTALL_DIR"; then
    INSTALL_MODE="update"
else
    INSTALL_MODE="fresh"
fi

if [[ "$INSTALL_MODE" == "update" ]]; then
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     Message Guard — به‌روزرسانی             ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
else
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║       Message Guard — نصب ربات شخصی         ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    warn "این ربات شخصی است — فقط روی سرور خودتان نصب کنید."
fi
echo ""
info "مسیر نصب: ${INSTALL_DIR}"
echo ""

command -v python3 >/dev/null 2>&1 || fail "python3 نصب نیست."
info "Python $(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
python3 -c 'import venv' 2>/dev/null || fail "python3-venv نصب نیست: sudo apt install python3-venv"
command -v curl >/dev/null 2>&1 || fail "curl نصب نیست: sudo apt install curl"

RSYNC_EXCLUDES=(
    --exclude 'config.json'
    --exclude 'session/'
    --exclude 'data/'
    --exclude 'media/'
    --exclude 'venv/'
    --exclude 'logs/'
)

download_source_to() {
    local dest="$1"
    mkdir -p "$dest"

    if command -v git >/dev/null 2>&1; then
        info "دریافت از GitHub (git)..."
        local tmpclone
        tmpclone="$(mktemp -d)"
        git clone --depth 1 --branch "$DEFAULT_BRANCH" "$REPO_URL" "${tmpclone}/repo"
        rsync -a "${RSYNC_EXCLUDES[@]}" "${tmpclone}/repo/" "$dest/"
        rm -rf "$tmpclone"
        return
    fi

    command -v tar >/dev/null 2>&1 || fail "git یا tar لازم است: sudo apt install git"
    command -v rsync >/dev/null 2>&1 || fail "rsync لازم است: sudo apt install rsync"

    info "دریافت از GitHub (آرشیو)..."
    local tmpdir
    tmpdir="$(mktemp -d)"
    curl -fsSL "$ARCHIVE_URL" -o "${tmpdir}/src.tar.gz"
    tar xzf "${tmpdir}/src.tar.gz" -C "$tmpdir"
    local extracted="${tmpdir}/puppy-${DEFAULT_BRANCH}"
    [[ -d "$extracted" ]] || fail "ساختار آرشیو GitHub غیرمنتظره بود"
    rsync -a "${RSYNC_EXCLUDES[@]}" "${extracted}/" "$dest/"
    rm -rf "$tmpdir"
}

sync_code() {
    mkdir -p "$INSTALL_DIR"

    if [[ "$INSTALL_MODE" == "update" && -d "${INSTALL_DIR}/.git" ]]; then
        info "به‌روزرسانی از GitHub (git pull)..."
        git -C "$INSTALL_DIR" fetch origin "$DEFAULT_BRANCH" --depth 1
        git -C "$INSTALL_DIR" reset --hard "origin/${DEFAULT_BRANCH}"
        ok "کد به‌روز شد"
        return
    fi

    if [[ "$INSTALL_MODE" == "update" ]]; then
        info "به‌روزرسانی از GitHub..."
    else
        info "دریافت پروژه از GitHub..."
    fi
    download_source_to "$INSTALL_DIR"
    ok "کد از GitHub دریافت شد (config و session و data حفظ شدند)"
}

sync_code

if ! has_install_at "$INSTALL_DIR"; then
    fail "دریافت کد ناموفق بود — main.py در ${INSTALL_DIR} یافت نشد"
fi

save_install_dir
cd "$INSTALL_DIR"
refresh_local_install_script

mkdir -p data session logs media

if [[ ! -f "${VENV_DIR}/bin/python" ]]; then
    info "ساخت محیط مجازی..."
    python3 -m venv "$VENV_DIR"
fi

info "نصب وابستگی‌های Python..."
"${VENV_DIR}/bin/pip" install --upgrade pip -q
"${VENV_DIR}/bin/pip" install -r requirements.txt -q
ok "پکیج‌ها نصب شدند"

if [[ -f "$CONFIG_FILE" ]]; then
    ok "config.json حفظ شد"
elif [[ -f "$EXAMPLE_FILE" ]]; then
    cp "$EXAMPLE_FILE" "$CONFIG_FILE"
    echo ""
    info "bot_token (BotFather) و super_admin_id (@userinfobot):"
    read -rp "  bot_token: " BOT_TOKEN
    read -rp "  super_admin_id: " SUPER_ADMIN
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
    fail "config.example.json یافت نشد"
fi

"${VENV_DIR}/bin/python" -c "from app.config import AppConfig; AppConfig.load()" \
    || fail "config.json نامعتبر است"
ok "پیکربندی معتبر است"

"${VENV_DIR}/bin/python" -c "
import asyncio
from app.config import AppConfig
from app.db.session import init_db
asyncio.run(init_db(AppConfig.load()))
"
ok "دیتابیس آماده است"

if [[ "$INSTALL_MODE" == "update" ]] && command -v systemctl >/dev/null 2>&1; then
    if systemctl is-enabled puppy >/dev/null 2>&1; then
        info "ری‌استارت سرویس puppy..."
        if [[ $EUID -eq 0 ]]; then
            systemctl restart puppy
        elif command -v sudo >/dev/null 2>&1; then
            sudo systemctl restart puppy
        fi
        ok "سرویس ری‌استارت شد"
    fi
fi

echo ""
echo -e "${GREEN}  ✔ $([[ "$INSTALL_MODE" == "update" ]] && echo به‌روزرسانی || echo نصب) انجام شد${NC}"
echo ""
echo "  مسیر:  ${INSTALL_DIR}"
echo "  اجرا:  ${VENV_DIR}/bin/python main.py run"
echo ""
echo "  آپدیت بعدی:"
echo "    curl -fsSL ${RAW_INSTALL_URL} | bash -s -- -u"
echo ""

if [[ "$SKIP_SERVICE_PROMPT" -eq 0 && "$INSTALL_MODE" == "fresh" ]]; then
    read -rp "نصب سرویس systemd؟ [y/N] " INSTALL_SERVICE
    if [[ "${INSTALL_SERVICE,,}" == y* ]]; then
        if [[ $EUID -eq 0 ]]; then
            bash "${INSTALL_DIR}/install-service.sh"
        else
            sudo bash "${INSTALL_DIR}/install-service.sh"
        fi
    fi
fi
