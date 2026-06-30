#!/usr/bin/env bash
# Message Guard (Puppy) — نصب / به‌روزرسانی مستقیم از GitHub
# https://github.com/Noctis-Architect/puppy
#
# نصب:
#   curl -fsSL https://raw.githubusercontent.com/Noctis-Architect/puppy/main/install.sh | bash
#
# به‌روزرسانی:
#   curl -fsSL https://raw.githubusercontent.com/Noctis-Architect/puppy/main/install.sh | bash -s -- -u
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

گزینه‌ها: -u  آپدیت | --fresh  نصب تازه | --dir PATH  مسیر نصب | --no-service
HELP
            exit 0
            ;;
        *) fail "گزینه ناشناخته: $1 (از --help استفاده کنید)" ;;
    esac
done

is_piped_install() {
    local script_path="${BASH_SOURCE[0]:-$0}"
    [[ "$script_path" == /dev/fd/* || "$script_path" == /proc/* ]]
}

resolve_install_dir() {
    if [[ -n "${PUPPY_INSTALL_DIR:-}" ]]; then
        echo "$PUPPY_INSTALL_DIR"
        return
    fi
    if [[ -f "$MARKER_FILE" ]]; then
        local saved
        saved="$(tr -d '\n' < "$MARKER_FILE")"
        if [[ -n "$saved" ]]; then
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
        if [[ -f "${script_dir}/main.py" ]]; then
            echo "$script_dir"
            return
        fi
    fi
    echo "${HOME}/puppy"
}

INSTALL_DIR="$(resolve_install_dir)"
INSIDE_REPO=0
if [[ -f "${INSTALL_DIR}/main.py" ]]; then
    INSIDE_REPO=1
fi

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

# آپدیت خودکار فقط اگر قبلاً نصب شده (مگر --fresh)
if [[ "$FORCE_FRESH" -eq 0 && "$UPDATE_MODE" -eq 0 ]]; then
    if [[ -f "$CONFIG_FILE" || -f "$MARKER_FILE" ]]; then
        UPDATE_MODE=1
    fi
fi

# نصب تازه از curl وقتی پوشه از قبل پر است
if [[ "$UPDATE_MODE" -eq 0 && "$INSIDE_REPO" -eq 0 && -d "$INSTALL_DIR" ]]; then
    if [[ "$(ls -A "$INSTALL_DIR" 2>/dev/null | wc -l)" -gt 0 ]]; then
        fail "پوشه ${INSTALL_DIR} خالی نیست. برای آپدیت: curl ... | bash -s -- -u"
    fi
fi

if [[ "$UPDATE_MODE" -eq 1 ]]; then
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

sync_from_github() {
    local mode="$1"

    if command -v git >/dev/null 2>&1; then
        if [[ "$mode" == "fresh" ]]; then
            mkdir -p "$(dirname "$INSTALL_DIR")"
            info "دریافت پروژه از GitHub (git clone)..."
            git clone --depth 1 --branch "$DEFAULT_BRANCH" "$REPO_URL" "$INSTALL_DIR"
        else
            [[ -d "${INSTALL_DIR}/.git" ]] || fail "ریپوی git یافت نشد در ${INSTALL_DIR}"
            info "به‌روزرسانی از GitHub (git)..."
            git -C "$INSTALL_DIR" fetch origin "$DEFAULT_BRANCH" --depth 1
            git -C "$INSTALL_DIR" reset --hard "origin/${DEFAULT_BRANCH}"
        fi
        ok "کد از GitHub دریافت شد"
        return
    fi

    command -v tar >/dev/null 2>&1 || fail "git یا tar لازم است: sudo apt install git"
    local tmpdir
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' RETURN

    info "دریافت پروژه از GitHub (آرشیو)..."
    curl -fsSL "$ARCHIVE_URL" -o "${tmpdir}/src.tar.gz"
    tar xzf "${tmpdir}/src.tar.gz" -C "$tmpdir"
    local extracted="${tmpdir}/puppy-${DEFAULT_BRANCH}"
    [[ -d "$extracted" ]] || fail "ساختار آرشیو غیرمنتظره بود"

    if [[ "$mode" == "fresh" ]]; then
        mkdir -p "$INSTALL_DIR"
        shopt -s dotglob
        mv "${extracted}"/* "$INSTALL_DIR/"
        shopt -u dotglob
    else
        command -v rsync >/dev/null 2>&1 || fail "rsync لازم است: sudo apt install rsync"
        rsync -a --delete \
            --exclude 'config.json' \
            --exclude 'session/' \
            --exclude 'data/' \
            --exclude 'media/' \
            --exclude 'venv/' \
            --exclude 'logs/' \
            "${extracted}/" "${INSTALL_DIR}/"
    fi
    ok "کد از GitHub دریافت شد (config و session و data حفظ شدند)"
}

if [[ "$UPDATE_MODE" -eq 1 ]]; then
    if [[ "$INSIDE_REPO" -eq 0 && ! -f "${INSTALL_DIR}/main.py" ]]; then
        fail "نصب قبلی یافت نشد. ابتدا: curl -fsSL ${RAW_INSTALL_URL} | bash"
    fi
    if is_piped_install || [[ ! -f "${INSTALL_DIR}/main.py" ]] || [[ -d "${INSTALL_DIR}/.git" ]]; then
        sync_from_github update
    else
        ok "کد محلی — فقط وابستگی‌ها و دیتابیس به‌روز می‌شوند"
    fi
else
    if [[ "$INSIDE_REPO" -eq 1 ]]; then
        ok "نصب از داخل ریپوی موجود"
    else
        sync_from_github fresh
    fi
fi

save_install_dir
mkdir -p "$INSTALL_DIR"
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

if [[ "$UPDATE_MODE" -eq 1 ]] && command -v systemctl >/dev/null 2>&1; then
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
echo -e "${GREEN}  ✔ $([[ "$UPDATE_MODE" -eq 1 ]] && echo به‌روزرسانی || echo نصب) انجام شد${NC}"
echo ""
echo "  مسیر:  ${INSTALL_DIR}"
echo "  اجرا:  ${VENV_DIR}/bin/python main.py run"
echo ""
echo "  آپدیت بعدی:"
echo "    curl -fsSL ${RAW_INSTALL_URL} | bash -s -- -u"
echo ""

if [[ "$SKIP_SERVICE_PROMPT" -eq 0 && "$UPDATE_MODE" -eq 0 ]]; then
    read -rp "نصب سرویس systemd؟ [y/N] " INSTALL_SERVICE
    if [[ "${INSTALL_SERVICE,,}" == y* ]]; then
        if [[ $EUID -eq 0 ]]; then
            bash "${INSTALL_DIR}/install-service.sh"
        else
            sudo bash "${INSTALL_DIR}/install-service.sh"
        fi
    fi
fi
