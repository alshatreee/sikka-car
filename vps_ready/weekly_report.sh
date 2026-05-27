#!/bin/bash
# Weekly report - runs Monday 9 AM UTC
# Collects status from all bots, sends summary to Telegram
# Cron: 0 9 * * 1 /root/bots/weekly_report.sh

set -euo pipefail

BOTS_DIR="/root/bots"
DATE=$(date +"%Y-%m-%d")
WEEK_AGO=$(date -d "7 days ago" +"%Y-%m-%d" 2>/dev/null || date -v-7d +"%Y-%m-%d")

# --- Telegram credentials ---
TOKEN=$(grep TELEGRAM_TOKEN "$BOTS_DIR/.env3" 2>/dev/null | cut -d= -f2 | head -1)
[ -z "$TOKEN" ] && TOKEN=$(grep TELEGRAM_TOKEN "$BOTS_DIR/.env2" 2>/dev/null | cut -d= -f2 | head -1)
[ -z "$TOKEN" ] && TOKEN=$(grep TELEGRAM_TOKEN "$BOTS_DIR/.env_naif" 2>/dev/null | cut -d= -f2 | head -1)
CHAT=$(grep TELEGRAM_CHAT_ID "$BOTS_DIR/.env3" 2>/dev/null | cut -d= -f2 | head -1)
[ -z "$CHAT" ] && CHAT=$(grep TELEGRAM_CHAT_ID "$BOTS_DIR/.env2" 2>/dev/null | cut -d= -f2 | head -1)

if [ -z "$TOKEN" ] || [ -z "$CHAT" ]; then
    echo "ERROR: Telegram credentials not found"
    exit 1
fi

# --- Bot services ---
SERVICES=(
    smart-copy-bot
    multi-strategy-bot
    naif-signal-bot
    paired-arb-bot
    resolution-sniper-bot
    monthly-channel-bot
    nautilus-ema-bot
    nautilus-rsi-bot
    nautilus-bb-bot
    markov-bot
)

MSG="📊 *Weekly Report* ($WEEK_AGO → $DATE)%0A%0A"

# Service status
MSG+="*Bot Status:*%0A"
for svc in "${SERVICES[@]}"; do
    STATUS=$(systemctl is-active "$svc" 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "active" ]; then
        ICON="✅"
    else
        ICON="❌"
    fi
    MSG+="$ICON $svc: $STATUS%0A"
done

# Trade counts and PnL from logs
TOTAL_TRADES=0
TOTAL_PNL=0
MSG+="%0A*Performance:*%0A"
for logfile in "$BOTS_DIR"/*.log; do
    [ -f "$logfile" ] || continue
    BOT=$(basename "$logfile" .log)
    TRADES=$(grep -c -i "BUY\|SELL\|OPEN" "$logfile" 2>/dev/null || echo 0)
    PNL=$(grep -oP 'PnL[:\s]*\K[+-]?\d+\.?\d*' "$logfile" 2>/dev/null | awk '{s+=$1} END {printf "%.2f", s+0}')
    TOTAL_TRADES=$((TOTAL_TRADES + TRADES))
    TOTAL_PNL=$(echo "$TOTAL_PNL + ${PNL:-0}" | bc 2>/dev/null || echo "$TOTAL_PNL")
    MSG+="$BOT: ${TRADES} trades, PnL: ${PNL:-0}%0A"
done

MSG+="%0A*Totals:* ${TOTAL_TRADES} trades | PnL: ${TOTAL_PNL}%0A"

# Disk & memory
DISK=$(df -h / | awk 'NR==2{print $5 " used"}')
MEM=$(free -h 2>/dev/null | awk 'NR==2{printf "%s/%s", $3, $2}' || echo "N/A")
MSG+="%0A*System:* Disk $DISK | RAM $MEM"

# Send to Telegram
curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d "chat_id=${CHAT}" \
    -d "text=${MSG}" \
    -d "parse_mode=Markdown" > /dev/null

echo "[OK] Weekly report sent - $DATE"
