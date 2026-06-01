#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/_common.sh"

DRY_RUN=false
SERVICE_NAME=portfolio-rag-assistant-letsencrypt-renew.service
TIMER_NAME=portfolio-rag-assistant-letsencrypt-renew.timer

usage() {
    cat <<'USAGE'
usage: public-certbot-install-timer.sh [--dry-run]

Install and enable the systemd timer that runs letsencrypt-renew.sh.
Run this on the deployment host from the repository checkout.
USAGE
}

run_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        require_command sudo
        sudo "$@"
    fi
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage >&2
            fail "unknown argument: $1"
            ;;
    esac
    shift
done

case "$ROOT_DIR" in
    *'
'*) fail "project path must not contain newlines" ;;
esac

configured_value PUBLIC_SERVER_NAME >/dev/null
configured_value LETSENCRYPT_EMAIL >/dev/null

SERVICE_FILE=$(mktemp)
TIMER_FILE=$(mktemp)
cleanup_files() {
    rm -f "$SERVICE_FILE" "$TIMER_FILE"
}
trap cleanup_files EXIT

cat > "$SERVICE_FILE" <<SERVICE
[Unit]
Description=Renew Portfolio RAG Assistant TLS certificate and reload Nginx
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$ROOT_DIR
Environment=ENV_FILE=$ENV_FILE
Environment=COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME
Environment=RUNTIME_WAIT_TIMEOUT_SECONDS=$RUNTIME_WAIT_TIMEOUT_SECONDS
ExecStart=$ROOT_DIR/scripts/runtime/letsencrypt-renew.sh
SERVICE

cat > "$TIMER_FILE" <<TIMER
[Unit]
Description=Run Portfolio RAG Assistant TLS renewal twice daily

[Timer]
OnCalendar=*-*-* 03,15:17:00
RandomizedDelaySec=1h
Persistent=true
Unit=$SERVICE_NAME

[Install]
WantedBy=timers.target
TIMER

if [ "$DRY_RUN" = true ]; then
    info "would install /etc/systemd/system/$SERVICE_NAME:"
    cat "$SERVICE_FILE"
    info "would install /etc/systemd/system/$TIMER_NAME:"
    cat "$TIMER_FILE"
    exit 0
fi

require_command systemctl

run_root install -m 0644 "$SERVICE_FILE" "/etc/systemd/system/$SERVICE_NAME"
run_root install -m 0644 "$TIMER_FILE" "/etc/systemd/system/$TIMER_NAME"
run_root systemctl daemon-reload
run_root systemctl enable --now "$TIMER_NAME"
systemctl list-timers "$TIMER_NAME" --no-pager
