#!/usr/bin/env bash
# SafeCross Edge Controller — installation script
# Run as root on the target DIN-rail ARM SBC.

set -euo pipefail

INSTALL_DIR="/opt/safecross"
CONFIG_DIR="/etc/safecross"
DATA_DIR="/var/lib/safecross"
VENV_DIR="${INSTALL_DIR}/venv"
SERVICE_FILE="/etc/systemd/system/safecross-edge.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"

echo "=== SafeCross Edge Controller Installer ==="
echo "  Project dir: ${PROJECT_DIR}"
echo

# ---------------------------------------------------------------
# 1. Check for root
# ---------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root." >&2
    exit 1
fi

# ---------------------------------------------------------------
# 2. Create system user and group
# ---------------------------------------------------------------
echo "[1/8] Creating safecross system user..."
if ! id -u safecross &>/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin safecross
    echo "       Created user 'safecross'"
else
    echo "       User 'safecross' already exists"
fi

# ---------------------------------------------------------------
# 3. Create directories
# ---------------------------------------------------------------
echo "[2/8] Creating directories..."
mkdir -p "${INSTALL_DIR}"
mkdir -p "${CONFIG_DIR}"
mkdir -p "${DATA_DIR}"
mkdir -p /tmp/safecross-update
mkdir -p /opt/safecross-staging

chown safecross:safecross "${DATA_DIR}"
chown safecross:safecross /tmp/safecross-update
chown safecross:safecross /opt/safecross-staging

echo "       ${INSTALL_DIR}"
echo "       ${CONFIG_DIR}"
echo "       ${DATA_DIR}"

# ---------------------------------------------------------------
# 4. Copy config (don't overwrite existing)
# ---------------------------------------------------------------
echo "[3/8] Installing configuration..."
if [[ ! -f "${CONFIG_DIR}/intersection.json" ]]; then
    if [[ -f "${PROJECT_DIR}/config/intersection.example.json" ]]; then
        cp "${PROJECT_DIR}/config/intersection.example.json" "${CONFIG_DIR}/intersection.json"
        chown safecross:safecross "${CONFIG_DIR}/intersection.json"
        chmod 640 "${CONFIG_DIR}/intersection.json"
        echo "       Copied example config → ${CONFIG_DIR}/intersection.json"
    else
        echo "       WARNING: No example config found at ${PROJECT_DIR}/config/intersection.example.json"
    fi
else
    echo "       Config already exists, not overwriting"
fi

# Copy schema (always update)
if [[ -f "${PROJECT_DIR}/config/schema.json" ]]; then
    cp "${PROJECT_DIR}/config/schema.json" "${CONFIG_DIR}/schema.json"
    echo "       Updated schema.json"
fi

# ---------------------------------------------------------------
# 5. Create Python venv
# ---------------------------------------------------------------
echo "[4/8] Creating Python virtual environment..."
if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
    echo "       Created venv at ${VENV_DIR}"
else
    echo "       Venv already exists"
fi

# ---------------------------------------------------------------
# 6. Install requirements
# ---------------------------------------------------------------
echo "[5/8] Installing Python dependencies..."
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet -r "${PROJECT_DIR}/requirements.txt"
echo "       Dependencies installed"

# ---------------------------------------------------------------
# 7. Install safecross package
# ---------------------------------------------------------------
echo "[6/8] Installing safecross package..."
"${VENV_DIR}/bin/pip" install --quiet -e "${PROJECT_DIR}"
echo "       Package installed (editable mode)"

# ---------------------------------------------------------------
# 8. Install systemd service
# ---------------------------------------------------------------
echo "[7/8] Installing systemd service..."
cp "${PROJECT_DIR}/scripts/safecross-edge.service" "${SERVICE_FILE}"
systemctl daemon-reload
systemctl enable safecross-edge
echo "       Service installed and enabled"

# ---------------------------------------------------------------
# 9. Install logrotate config
# ---------------------------------------------------------------
echo "[8/8] Installing logrotate config..."
if [[ -f "${PROJECT_DIR}/scripts/logrotate.conf" ]]; then
    cp "${PROJECT_DIR}/scripts/logrotate.conf" /etc/logrotate.d/safecross
    echo "       Logrotate config installed"
fi

# ---------------------------------------------------------------
# Done
# ---------------------------------------------------------------
echo
echo "============================================"
echo "  Installation complete."
echo
echo "  Next steps:"
echo "    1. Edit ${CONFIG_DIR}/intersection.json"
echo "       with your intersection's parameters"
echo "    2. Start the service:"
echo "       systemctl start safecross-edge"
echo "    3. Check status:"
echo "       systemctl status safecross-edge"
echo "       journalctl -u safecross-edge -f"
echo "============================================"
