#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash scripts/setup_vps.sh [WORKDIR] [USER]
# Example:
#   bash scripts/setup_vps.sh /opt/LINE_notify_tsukishima ubuntu

WORKDIR="${1:-/opt/LINE_notify_tsukishima}"
RUN_USER="${2:-$USER}"

echo "[+] WORKDIR: ${WORKDIR}"
echo "[+] USER   : ${RUN_USER}"

if [[ ! -d "${WORKDIR}" ]]; then
  echo "[+] Creating workdir and copying repository..."
  sudo mkdir -p "${WORKDIR}"
  sudo rsync -a --exclude 'venv' ./ "${WORKDIR}/"
  sudo chown -R "${RUN_USER}:${RUN_USER}" "${WORKDIR}"
fi

cd "${WORKDIR}"

echo "[+] Installing system prerequisites (requires sudo)"
sudo apt update -y
sudo apt install -y python3-venv python3-pip git rsync

echo "[+] Creating venv if missing"
if [[ ! -d venv ]]; then
  python3 -m venv venv
fi

echo "[+] Installing python deps"
"${WORKDIR}/venv/bin/python" -m pip install -U pip
"${WORKDIR}/venv/bin/pip" install -r requirements.txt

echo "[+] Installing Playwright deps and Chromium (requires sudo for system packages)"
sudo "${WORKDIR}/venv/bin/python" -m playwright install-deps || true
"${WORKDIR}/venv/bin/python" -m playwright install chromium

echo "[+] Ensuring subscribers.txt exists (placeholder)"
if [[ ! -s subscribers.txt ]]; then
  echo "placeholder" > subscribers.txt
fi

echo "[+] Ensuring .env exists"
if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "[#] Please edit ${WORKDIR}/.env to set LINE_CHANNEL_ACCESS_TOKEN"
  else
    cat > .env <<'EOF'
LINE_CHANNEL_ACCESS_TOKEN=
TARGET_URL=https://www.31sumai.com/attend/X1413/
CHECK_INTERVAL=2
EOF
    echo "[#] Please edit ${WORKDIR}/.env to set LINE_CHANNEL_ACCESS_TOKEN"
  fi
fi

echo "[+] Installing systemd unit and timer"
TMP_DIR="$(mktemp -d)"
sed -e "s|__WORKDIR__|${WORKDIR}|g" -e "s|__USER__|${RUN_USER}|g" \
  deploy/systemd/line-calendar-watch.service.template > "${TMP_DIR}/line-calendar-watch.service"
cp deploy/systemd/line-calendar-watch.timer.template "${TMP_DIR}/line-calendar-watch.timer"

sudo mv "${TMP_DIR}/line-calendar-watch.service" /etc/systemd/system/line-calendar-watch.service
sudo mv "${TMP_DIR}/line-calendar-watch.timer" /etc/systemd/system/line-calendar-watch.timer
rm -rf "${TMP_DIR}"

echo "[+] Enabling systemd timer"
sudo systemctl daemon-reload
sudo systemctl enable --now line-calendar-watch.timer

echo "[+] Checking status"
systemctl status line-calendar-watch.timer --no-pager || true
echo "[i] Tail logs: journalctl -u line-calendar-watch.service -n 100 -f --no-pager"
echo "[i] Data logs: tail -n 100 ${WORKDIR}/data/monitor.log"

echo "[✓] Setup complete"



