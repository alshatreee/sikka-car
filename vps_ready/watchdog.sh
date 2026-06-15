#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
#  Watchdog: keeps the live trading bots alive.
#  - Checks each bot every run; restarts any that died (they run
#    under nohup, so a server reboot or crash kills them silently).
#  - Logs to watchdog.log and sends a Telegram alert on restart.
#  Intended to run from cron, e.g.:  */5 * * * * /root/bots/watchdog.sh
# ──────────────────────────────────────────────────────────────
set -u

BOTS_DIR="/root/bots"
ENV_FILE="$BOTS_DIR/.env_monthly"
WLOG="$BOTS_DIR/watchdog.log"

# bot script name  ->  log file
BOTS=(monthly_channel_bot)

ts() { date '+%Y-%m-%d %H:%M:%S'; }

log() { echo "[$(ts)] $*" >> "$WLOG"; }

# Read TELEGRAM_TOKEN / TELEGRAM_CHAT_ID from .env_monthly (not hardcoded).
tg_get() {
    local key="$1"
    [ -f "$ENV_FILE" ] || return 0
    grep -E "^${key}=" "$ENV_FILE" | head -n1 | cut -d= -f2- | tr -d '\r'
}

notify() {
    local msg="$1"
    local token chat
    token="$(tg_get TELEGRAM_TOKEN)"
    chat="$(tg_get TELEGRAM_CHAT_ID)"
    [ -z "$token" ] || [ -z "$chat" ] && return 0
    curl -s -m 10 -o /dev/null \
        --data-urlencode "chat_id=${chat}" \
        --data-urlencode "text=${msg}" \
        "https://api.telegram.org/bot${token}/sendMessage" || true
}

cd "$BOTS_DIR" || { log "FATAL: cannot cd $BOTS_DIR"; exit 1; }

status_line=""
for bot in "${BOTS[@]}"; do
    # Count running instances of this exact bot (live).
    count=$(pgrep -fc "python3 ${bot}.py --live" || true)
    count=${count:-0}

    if [ "$count" -eq 0 ]; then
        nohup python3 "${bot}.py" --live >> "${bot}.log" 2>&1 &
        sleep 1
        log "RESTARTED ${bot} (was down)"
        notify "🔄 Watchdog: أعدت تشغيل ${bot} (كان متوقفاً)"
        status_line+="${bot}:restarted "
    elif [ "$count" -gt 1 ]; then
        # More than one copy → kill all and start a single clean instance.
        pkill -f "python3 ${bot}.py --live"
        sleep 2
        nohup python3 "${bot}.py" --live >> "${bot}.log" 2>&1 &
        sleep 1
        log "DEDUP ${bot} (had ${count} copies, restarted single)"
        notify "⚠️ Watchdog: ${bot} كان يعمل ${count} نسخ — أبقيت نسخة واحدة"
        status_line+="${bot}:dedup "
    else
        status_line+="${bot}:ok "
    fi
done

# Heartbeat so `tail watchdog.log` always shows the watchdog is alive.
log "heartbeat ${status_line}"

# Cap the log so it can't grow without bound (~ last 2000 lines).
if [ -f "$WLOG" ] && [ "$(wc -l < "$WLOG")" -gt 2000 ]; then
    tail -n 1000 "$WLOG" > "$WLOG.tmp" && mv "$WLOG.tmp" "$WLOG"
fi
