#!/usr/bin/env bash
# Message Guard (Puppy) — نصب / به‌روزرسانی از GitHub
# Installer v3.0.3
#
# نصب:   curl -fsSL https://raw.githubusercontent.com/Noctis-Architect/puppy/main/install.sh | bash
# آپدیت: curl -fsSL https://raw.githubusercontent.com/Noctis-Architect/puppy/main/install.sh | bash -s -- -u
set -eo pipefail

INSTALLER_VERSION="3.0.3"

GITHUB_REPO="Noctis-Architect/puppy"
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

# curl | bash uses stdin for the script; read must use the terminal.
prompt_tty() {
    local prompt="$1"
    local var="$2"
    if [[ -r /dev/tty ]]; then
        read -rp "$prompt" "$var" </dev/tty
    elif [[ -n "${!var:-}" ]]; then
        return 0
    else
        fail "ورودی تعاملی لازم است (یا ${var} را export کنید)"
    fi
}

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
            echo "Installer v${INSTALLER_VERSION}"
            echo "نصب:   curl -fsSL ${RAW_INSTALL_URL} | bash"
            echo "آپدیت: curl -fsSL ${RAW_INSTALL_URL} | bash -s -- -u"
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
        if [[ -n "$saved" ]]; then
            echo "$saved"
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
    curl -fsSL "$RAW_INSTALL_URL" -o "${INSTALL_DIR}/install.sh" 2>/dev/null && \
        chmod +x "${INSTALL_DIR}/install.sh" || true
}

if [[ "$FORCE_FRESH" -eq 1 ]]; then
    INSTALL_MODE="fresh"
elif [[ "$UPDATE_MODE" -eq 1 ]]; then
    if has_install_at "$INSTALL_DIR"; then
        INSTALL_MODE="update"
    else
        warn "نصب ناقص — در حال ترمیم..."
        INSTALL_MODE="fresh"
    fi
elif has_install_at "$INSTALL_DIR"; then
    INSTALL_MODE="update"
else
    INSTALL_MODE="fresh"
fi

echo ""
info "Installer v${INSTALLER_VERSION} — $([[ "$INSTALL_MODE" == "update" ]] && echo به‌روزرسانی || echo نصب)"
info "مسیر نصب: ${INSTALL_DIR}"
echo ""

command -v python3 >/dev/null 2>&1 || fail "python3 نصب نیست."
command -v curl >/dev/null 2>&1 || fail "curl نصب نیست."
command -v tar >/dev/null 2>&1 || fail "tar نصب نیست."
python3 -c 'import venv' 2>/dev/null || fail "python3-venv نصب نیست: sudo apt install python3-venv"

_should_skip_name() {
    case "$1" in
        config.json|session|data|media|venv|logs) return 0 ;;
        *) return 1 ;;
    esac
}

merge_from_archive() {
    local src="$1"
    local dest="$2"
    mkdir -p "$dest"

    shopt -s dotglob nullglob
    for entry in "${src}"/*; do
        [[ -e "$entry" ]] || continue
        local name="${entry##*/}"
        _should_skip_name "$name" && continue
        rm -rf "${dest:?}/${name}"
        cp -a "$entry" "${dest}/${name}"
    done
    shopt -u dotglob nullglob
}

download_and_merge() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' RETURN

    info "دانلود از GitHub..."
    curl -fsSL "$ARCHIVE_URL" -o "${tmpdir}/src.tar.gz"
    tar xzf "${tmpdir}/src.tar.gz" -C "$tmpdir"

    local extracted="${tmpdir}/puppy-${DEFAULT_BRANCH}"
    [[ -d "$extracted" ]] || fail "ساختار آرشیو GitHub غیرمنتظره بود"

    merge_from_archive "$extracted" "$INSTALL_DIR"
    ok "فایل‌ها کپی شدند (config / session / data / venv حفظ شدند)"
}

sync_code() {
    mkdir -p "$INSTALL_DIR"

    if [[ "$INSTALL_MODE" == "update" && -d "${INSTALL_DIR}/.git" ]] && command -v git >/dev/null 2>&1; then
        info "به‌روزرسانی با git..."
        git -C "$INSTALL_DIR" fetch origin "$DEFAULT_BRANCH" --depth 1 2>/dev/null || true
        if git -C "$INSTALL_DIR" rev-parse "origin/${DEFAULT_BRANCH}" >/dev/null 2>&1; then
            git -C "$INSTALL_DIR" reset --hard "origin/${DEFAULT_BRANCH}"
            ok "کد به‌روز شد (git)"
            return
        fi
        warn "git ناموفق — fallback به آرشیو"
    fi

    download_and_merge
}

sync_code

has_install_at "$INSTALL_DIR" || fail "main.py در ${INSTALL_DIR} نیست — دانلود ناموفق بود"

save_install_dir
cd "$INSTALL_DIR"
refresh_local_install_script
mkdir -p data session logs media

if [[ ! -f "${VENV_DIR}/bin/python" ]]; then
    info "ساخت venv..."
    python3 -m venv "$VENV_DIR"
fi

info "نصب پکیج‌ها..."
"${VENV_DIR}/bin/pip" install --upgrade pip -q
"${VENV_DIR}/bin/pip" install -r requirements.txt -q
ok "پکیج‌ها نصب شدند"

if [[ -f "$CONFIG_FILE" ]]; then
    ok "config.json حفظ شد"
elif [[ -f "$EXAMPLE_FILE" ]]; then
    cp "$EXAMPLE_FILE" "$CONFIG_FILE"
    BOT_TOKEN="${PUPPY_BOT_TOKEN:-}"
    SUPER_ADMIN="${PUPPY_SUPER_ADMIN_ID:-}"
    echo ""
    [[ -z "$BOT_TOKEN" ]] && prompt_tty "  bot_token: " BOT_TOKEN
    [[ -z "$SUPER_ADMIN" ]] && prompt_tty "  super_admin_id: " SUPER_ADMIN
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

"${VENV_DIR}/bin/python" -c "
import asyncio
from app.config import AppConfig
from app.db.session import init_db
asyncio.run(init_db(AppConfig.load()))
"
ok "دیتابیس آماده"

if [[ "$INSTALL_MODE" == "update" ]] && command -v systemctl >/dev/null 2>&1; then
    if systemctl is-enabled puppy >/dev/null 2>&1; then
        if [[ $EUID -eq 0 ]]; then systemctl restart puppy
        elif command -v sudo >/dev/null 2>&1; then sudo systemctl restart puppy
        fi
        ok "سرویس restart شد"
    fi
fi

echo ""
echo -e "${GREEN}  ✔ تمام${NC} — ${INSTALL_DIR}"
echo "  اجرا: ${VENV_DIR}/bin/python main.py run"
echo ""

if [[ "$SKIP_SERVICE_PROMPT" -eq 0 && "$INSTALL_MODE" == "fresh" ]]; then
    INSTALL_SERVICE="${PUPPY_INSTALL_SERVICE:-}"
    if [[ -z "$INSTALL_SERVICE" ]]; then
        if [[ -r /dev/tty ]]; then
            prompt_tty "نصب systemd? [y/N] " INSTALL_SERVICE
        else
            INSTALL_SERVICE=n
        fi
    fi
    case "${INSTALL_SERVICE,,}" in
        y|yes) INSTALL_SERVICE=y ;;
        *) INSTALL_SERVICE=n ;;
    esac
    if [[ "$INSTALL_SERVICE" == y ]]; then
        if [[ $EUID -eq 0 ]]; then bash "${INSTALL_DIR}/install-service.sh"
        else sudo bash "${INSTALL_DIR}/install-service.sh"; fi
    fi
fi
