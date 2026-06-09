"""
bot_monitor.py — مراقب وتحليل بوت القناة الشهرية

يفحص كل 15 دقيقة:
- حالة خدمة systemd (شغالة / إعادة تشغيل متكررة / متجمدة)
- أخطاء المنصات وأوامر التداول في اللوق
- أنماط غريبة: تكرار شراء عملة، رصيد غير كافٍ متكرر، إيقاف التداول
- توقف تحديث اللوق (تجمّد البوت)

ينبه على التيليجرام عند اكتشاف مشكلة جديدة (بدون إعادة تشغيل).

    python3 bot_monitor.py            # تشغيل مستمر
    python3 bot_monitor.py --once     # فحص واحد + تقرير
    python3 bot_monitor.py --report   # تقرير صحة فوري

    pip install python-dotenv requests
"""
from __future__ import annotations
import json, os, re, subprocess, sys, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(r"C:\Users\xman9\Desktop") if os.name == "nt" else Path("/root/bots")
BASE_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = BASE_DIR / ".env_monthly"
TARGET_LOG = BASE_DIR / "monthly.log"
STATE_FILE = BASE_DIR / "monitor_state.json"
LOG_FILE = BASE_DIR / "monitor.log"
load_dotenv(ENV_FILE if ENV_FILE.exists() else None)

SERVICE_NAME = os.getenv("MONITOR_SERVICE", "monthly-channel-bot")
NOTIFY_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
NOTIFY_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
CEREBRAS_KEY = os.getenv("CEREBRAS_API_KEY", "")

RAW_MSGS_FILE = BASE_DIR / "channel_raw_messages.json"
AI_ANALYSIS_FILE = BASE_DIR / "ai_channel_analysis.json"

CHECK_INTERVAL = int(os.getenv("MONITOR_CHECK_SEC", "900"))
LOG_STALE_MIN = int(os.getenv("MONITOR_LOG_STALE_MIN", "30"))
AUTO_RESTART = os.getenv("MONITOR_AUTO_RESTART", "true").lower() == "true"
MAX_RESTARTS_HR = int(os.getenv("MONITOR_MAX_RESTARTS", "4"))
DUP_BUY_WINDOW = int(os.getenv("MONITOR_DUP_WINDOW", "20"))
INSUFFICIENT_LIMIT = int(os.getenv("MONITOR_INSUFFICIENT_LIMIT", "10"))
DAILY_SUMMARY_HOUR = int(os.getenv("MONITOR_SUMMARY_HOUR", "21"))

_IS_TTY = sys.stdin and sys.stdin.isatty()

# أنماط الأخطاء في اللوق — (المفتاح, التعبير, الخطورة)
ERROR_PATTERNS = [
    ("exchange_down", r"خطأ (KuCoin|Bybit):", "🔴 منصة"),
    ("buy_error", r"خطأ في الشراء:", "🔴 شراء"),
    ("sell_error", r"خطأ في البيع:", "🔴 بيع"),
    ("sl_error", r"خطأ وقف الخسارة:", "🟠 وقف خسارة"),
    ("sl_check_error", r"فحص أمر SL", "🟠 فحص وقف"),
    ("balance_error", r"خطأ جلب الرصيد:", "🟠 رصيد"),
    ("check_error", r"خطأ في فحص", "🟠 فحص"),
    ("notify_error", r"خطأ في الإشعار:", "🟡 إشعار"),
    ("halt", r"إيقاف التداول", "🔴 إيقاف تداول"),
    ("insufficient", r"رصيد غير كافٍ", "🟡 رصيد ناقص"),
    ("dup_position", r"مركز مفتوح بالفعل|العملة مفتوحة بالفعل", "🟡 تكرار"),
    ("symbol_missing", r"الزوج غير موجود", "🟡 زوج مفقود"),
]

# شرح كل خطأ + اقتراح الحل
ERROR_DIAGNOSIS = {
    "exchange_down": {
        "explain": "المنصة لا تستجيب — قد تكون معطلة مؤقتاً أو مفاتيح API منتهية",
        "fix": "تحقق من حالة المنصة وصلاحية مفاتيح API في ملف .env_monthly",
        "severity": "عالي",
    },
    "buy_error": {
        "explain": "فشل تنفيذ أمر الشراء — الرصيد غير كافٍ أو الزوج غير متاح أو حد أدنى غير محقق",
        "fix": "تحقق من رصيد USDT في المنصة وتأكد أن العملة متاحة للتداول الفوري",
        "severity": "عالي",
    },
    "sell_error": {
        "explain": "فشل تنفيذ أمر البيع — الكمية أقل من الحد الأدنى أو العملة محظورة",
        "fix": "تحقق من الكمية المتاحة في محفظة المنصة وحدود التداول الأدنى",
        "severity": "عالي",
    },
    "sl_error": {
        "explain": "فشل وضع أمر وقف الخسارة على المنصة",
        "fix": "البوت يستخدم فحص السعر كبديل احتياطي — لا خطر فوري",
        "severity": "متوسط",
    },
    "sl_check_error": {
        "explain": "فشل فحص حالة أمر وقف الخسارة — غالباً مشكلة API مع المنصة",
        "fix": "إذا تكرر: حدّث البوت لآخر نسخة. البوت يفحص السعر يدوياً كاحتياط",
        "severity": "متوسط",
    },
    "balance_error": {
        "explain": "فشل جلب رصيد المحفظة من المنصة",
        "fix": "تحقق من صلاحيات API — يجب أن تشمل 'قراءة الرصيد'",
        "severity": "متوسط",
    },
    "check_error": {
        "explain": "خطأ أثناء فحص المراكز المفتوحة أو جلب الأسعار",
        "fix": "غالباً مؤقت بسبب ضغط على المنصة — إذا تكرر باستمرار تحقق من اتصال الإنترنت",
        "severity": "متوسط",
    },
    "notify_error": {
        "explain": "فشل إرسال إشعار تيليجرام — لا يؤثر على التداول",
        "fix": "تحقق من TELEGRAM_TOKEN و TELEGRAM_CHAT_ID في .env_monthly",
        "severity": "منخفض",
    },
    "halt": {
        "explain": "البوت أوقف التداول تلقائياً لأن الخسارة اليومية تجاوزت الحد المسموح",
        "fix": "راجع الصفقات المغلقة اليوم — التداول يستأنف تلقائياً غداً",
        "severity": "عالي",
    },
    "insufficient": {
        "explain": "الرصيد المتاح أقل من حجم الصفقة المطلوب ($100)",
        "fix": "حوّل USDT للمحفظة الفورية (Spot) أو قلّل MONTHLY_BYBIT_TRADE_SIZE",
        "severity": "متوسط",
    },
    "dup_position": {
        "explain": "البوت تجاهل توصية لأن العملة مفتوحة بالفعل — سلوك طبيعي",
        "fix": "لا إجراء مطلوب — هذا حماية من الشراء المزدوج",
        "severity": "معلومة",
    },
    "symbol_missing": {
        "explain": "العملة غير موجودة في المنصتين (Bybit و KuCoin)",
        "fix": "العملة قد تكون جديدة أو غير مدرجة — البوت يتجاهلها تلقائياً",
        "severity": "منخفض",
    },
}


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}"
    if _IS_TTY:
        print(line, flush=True)
    try:
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def notify(msg: str) -> None:
    if not NOTIFY_TOKEN or not NOTIFY_CHAT:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{NOTIFY_TOKEN}/sendMessage",
            json={"chat_id": NOTIFY_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        log(f"خطأ إرسال: {e}")


@dataclass
class MonitorState:
    log_offset: int = 0
    last_summary_day: str = ""
    last_alert_hashes: list[str] = field(default_factory=list)
    error_counts: dict[str, int] = field(default_factory=dict)


def load_state() -> MonitorState:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            return MonitorState(**{k: v for k, v in data.items()
                                  if k in MonitorState.__dataclass_fields__})
        except Exception:
            pass
    return MonitorState()


def save_state(state: MonitorState):
    STATE_FILE.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2))


def read_new_lines(state: MonitorState) -> list[str]:
    """قراءة الأسطر الجديدة من اللوق منذ آخر فحص"""
    if not TARGET_LOG.exists():
        return []
    size = TARGET_LOG.stat().st_size
    if state.log_offset > size:
        state.log_offset = 0  # اللوق دُوّر/أُفرغ
    with TARGET_LOG.open("r", errors="replace") as f:
        f.seek(state.log_offset)
        lines = f.readlines()
        state.log_offset = f.tell()
    return lines


def service_status() -> dict:
    """حالة خدمة systemd"""
    info = {"active": False, "restarts": 0, "sub": "?", "since": "?"}
    try:
        out = subprocess.run(
            ["systemctl", "show", SERVICE_NAME,
             "-p", "ActiveState,SubState,NRestarts,ActiveEnterTimestamp"],
            capture_output=True, text=True, timeout=15,
        ).stdout
        for line in out.splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k == "ActiveState":
                info["active"] = (v == "active")
            elif k == "SubState":
                info["sub"] = v
            elif k == "NRestarts":
                info["restarts"] = int(v) if v.isdigit() else 0
            elif k == "ActiveEnterTimestamp":
                info["since"] = v
    except Exception as e:
        log(f"خطأ حالة الخدمة: {e}")
    return info


def log_age_minutes() -> float:
    if not TARGET_LOG.exists():
        return 1e9
    return (time.time() - TARGET_LOG.stat().st_mtime) / 60


def analyze_lines(lines: list[str]) -> dict:
    """تحليل الأسطر الجديدة واكتشاف المشاكل"""
    findings = {"errors": {}, "buys": [], "insufficient": 0, "details": []}

    for line in lines:
        for key, pat, label in ERROR_PATTERNS:
            if re.search(pat, line):
                findings["errors"].setdefault(key, {"label": label, "count": 0, "sample": ""})
                findings["errors"][key]["count"] += 1
                if not findings["errors"][key]["sample"]:
                    findings["errors"][key]["sample"] = line.strip()[-160:]

        m = re.search(r"أمر شراء: ([A-Z0-9]+)/USDT", line)
        if m:
            findings["buys"].append(m.group(1))

        if "رصيد غير كافٍ" in line:
            findings["insufficient"] += 1

    return findings


def detect_duplicate_buys(buys: list[str]) -> dict:
    """اكتشاف تكرار شراء نفس العملة في نافذة قريبة"""
    dups = {}
    counts = {}
    for sym in buys[-DUP_BUY_WINDOW:]:
        counts[sym] = counts.get(sym, 0) + 1
    for sym, c in counts.items():
        if c >= 2:
            dups[sym] = c
    return dups


def auto_restart(reason: str) -> bool:
    """إعادة تشغيل البوت تلقائياً وإرجاع True إذا نجح"""
    try:
        subprocess.run(["systemctl", "restart", SERVICE_NAME],
                       capture_output=True, timeout=30)
        log(f"✅ إعادة تشغيل تلقائية: {reason}")
        return True
    except Exception as e:
        log(f"❌ فشل إعادة التشغيل: {e}")
        return False


def run_checks(state: MonitorState, send_ok: bool = False) -> list[str]:
    """تشغيل كل الفحوصات وإرجاع قائمة التنبيهات"""
    alerts = []

    # 1) حالة الخدمة
    svc = service_status()
    if not svc["active"]:
        if AUTO_RESTART:
            restarted = auto_restart("البوت متوقف")
            status_msg = "✅ تمت إعادة التشغيل تلقائياً" if restarted else "❌ فشلت إعادة التشغيل — تدخل يدوي مطلوب"
        else:
            status_msg = f"الحل: شغّل <code>systemctl restart {SERVICE_NAME}</code>"
        alerts.append(
            f"🔴 <b>البوت متوقف!</b>\n"
            f"الحالة: {svc['sub']}\n"
            f"السبب: الخدمة توقفت — قد يكون خطأ برمجي أو نفاد الذاكرة\n"
            f"{status_msg}"
        )
    if svc["restarts"] > MAX_RESTARTS_HR:
        alerts.append(
            f"🟠 <b>إعادة تشغيل متكررة</b>\n"
            f"عدد المرات: {svc['restarts']}\n"
            f"السبب: البوت يتوقف ويعاد تشغيله باستمرار — غالباً خطأ متكرر\n"
            f"الحل: راجع <code>journalctl -u {SERVICE_NAME} --no-pager -n 50</code>"
        )

    # 2) تجمّد اللوق — إعادة تشغيل تلقائية
    age = log_age_minutes()
    if svc["active"] and age > LOG_STALE_MIN:
        if AUTO_RESTART:
            restarted = auto_restart(f"اللوق متوقف منذ {age:.0f} دقيقة")
            status_msg = "✅ تمت إعادة التشغيل تلقائياً" if restarted else "❌ فشلت إعادة التشغيل"
        else:
            status_msg = f"الحل: <code>systemctl restart {SERVICE_NAME}</code>"
        alerts.append(
            f"🟠 <b>البوت متجمّد — تمت إعادة تشغيله</b>\n"
            f"آخر تحديث: قبل {age:.0f} دقيقة\n"
            f"{status_msg}"
        )

    # 3) تحليل الأسطر الجديدة
    lines = read_new_lines(state)
    findings = analyze_lines(lines)

    for key, data in findings["errors"].items():
        state.error_counts[key] = state.error_counts.get(key, 0) + data["count"]
        diag = ERROR_DIAGNOSIS.get(key, {})
        explain = diag.get("explain", "خطأ غير معروف")
        fix = diag.get("fix", "راجع اللوق يدوياً")
        severity = diag.get("severity", "?")
        alerts.append(
            f"{data['label']} <b>خطأ ({data['count']}×)</b>\n"
            f"الخطورة: {severity}\n"
            f"السبب: {explain}\n"
            f"الحل: {fix}\n"
            f"<code>{data['sample']}</code>"
        )

    # 4) تكرار شراء عملة
    dups = detect_duplicate_buys(findings["buys"])
    if dups:
        d = "\n".join(f"  {s}: {c}×" for s, c in dups.items())
        alerts.append(
            f"🔴 <b>تكرار شراء عملة!</b>\n{d}\n"
            f"السبب: البوت اشترى نفس العملة أكثر من مرة — قد يكون خلل في حفظ المراكز\n"
            f"الحل: حدّث البوت لآخر نسخة وتحقق من ملف الحالة monthly_state.json"
        )

    # 5) رصيد غير كافٍ متكرر
    if findings["insufficient"] >= INSUFFICIENT_LIMIT:
        alerts.append(
            f"🟡 <b>رصيد غير كافٍ متكرر</b>\n"
            f"{findings['insufficient']} محاولة فاشلة\n"
            f"السبب: رصيد USDT أقل من حجم الصفقة ($100)\n"
            f"الحل: حوّل USDT إلى المحفظة الفورية (Spot) في المنصة"
        )

    save_state(state)
    return alerts


def build_health_report(state: MonitorState) -> str:
    svc = service_status()
    age = log_age_minutes()
    status = "🟢 شغّال" if svc["active"] else "🔴 متوقف"
    lines = [
        f"<b>🩺 تقرير صحة البوت</b>\n",
        f"الخدمة: {status} ({svc['sub']})",
        f"إعادة التشغيل: {svc['restarts']}×",
        f"آخر تحديث لوق: قبل {age:.0f} دقيقة",
    ]
    if state.error_counts:
        lines.append("\n<b>إجمالي الأخطاء المرصودة:</b>")
        for key, count in state.error_counts.items():
            label = next((l for k, p, l in ERROR_PATTERNS if k == key), key)
            diag = ERROR_DIAGNOSIS.get(key, {})
            fix = diag.get("fix", "")
            lines.append(f"  {label}: {count}×")
            if fix:
                lines.append(f"    ↳ {fix}")
    else:
        lines.append("\n✅ لا أخطاء مرصودة — البوت يعمل بشكل سليم")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# AI CHANNEL ANALYSIS (Cerebras)
# ══════════════════════════════════════════════════════════════

_ai_last_run = 0
_AI_INTERVAL = 600  # every 10 min

def _cerebras_analyze(messages_text: str) -> dict | None:
    if not CEREBRAS_KEY:
        return None
    import urllib.request as req
    prompt = (
        "أنت محلل عملات رقمية محترف. حلل رسائل القنوات التالية واستخرج:\n"
        "1. أي عملة مذكورة بإيجابية (شراء/صعود/بول ران/بامب/اختراق/فرصة/أي توصية إيجابية)\n"
        "2. أي عملة مذكورة بسلبية (بيع/هبوط/دامب/تحذير)\n"
        "3. مستوى الثقة (high/medium/low)\n\n"
        "افهم المصطلحات المعرّبة: بول ران=bull run, بامب=pump, بريك اوت=breakout, "
        "لونق=long, شورت=short, دامب=dump, تارقت=target, ستوب لوس=stop loss, "
        "هودل=HODL, رالي=rally, مون=moon, سبورت=support, ريزستنس=resistance, "
        "تريند=trend, بيرش=bearish, بولش=bullish, اكيوميوليت=accumulate, "
        "دي سي ايه=DCA, ريكفري=recovery\n\n"
        "أجب بـ JSON فقط بهذا الشكل:\n"
        '{"buy":[{"symbol":"XRP","confidence":"high","reason":"بول ران + اختراق"}],'
        '"sell":[{"symbol":"BTC","confidence":"medium","reason":"هبوط"}],'
        '"watch":[{"symbol":"ETH","note":"ذكر بدون توصية واضحة"}]}\n\n'
        "الرسائل:\n" + messages_text
    )
    body = json.dumps({
        "model": "llama-4-scout-17b-16e-instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1000,
    })
    try:
        r = req.Request("https://api.cerebras.ai/v1/chat/completions",
                        data=body.encode(),
                        headers={"Content-Type": "application/json",
                                 "Authorization": f"Bearer {CEREBRAS_KEY}"})
        with req.urlopen(r, timeout=30) as resp:
            data = json.loads(resp.read())
        content = data["choices"][0]["message"]["content"]
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
    except Exception as e:
        log(f"Cerebras AI error: {e}")
    return None


def run_ai_analysis():
    global _ai_last_run
    now = time.time()
    if now - _ai_last_run < _AI_INTERVAL:
        return
    _ai_last_run = now

    if not CEREBRAS_KEY or not RAW_MSGS_FILE.exists():
        return

    try:
        raw = json.loads(RAW_MSGS_FILE.read_text())
    except Exception:
        return

    if not raw:
        return

    existing = {}
    if AI_ANALYSIS_FILE.exists():
        try:
            existing = json.loads(AI_ANALYSIS_FILE.read_text())
        except Exception:
            existing = {}

    seen_ids = set(existing.get("_seen_ids", []))
    new_msgs = [m for m in raw if str(m.get("msg_id", "")) not in seen_ids]
    if not new_msgs:
        return

    batch_text = ""
    for m in new_msgs[-30:]:
        batch_text += f"[{m.get('channel','')}] {m.get('text','')}\n---\n"

    if not batch_text.strip():
        return

    log(f"AI: تحليل {len(new_msgs)} رسالة جديدة...")
    result = _cerebras_analyze(batch_text)
    if not result:
        return

    buy_signals = existing.get("buy", [])
    sell_signals = existing.get("sell", [])
    watch_list = existing.get("watch", [])

    for sig in result.get("buy", []):
        sym = sig.get("symbol", "").upper()
        if sym and not any(s.get("symbol") == sym for s in buy_signals[-20:]):
            sig["symbol"] = sym
            sig["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            buy_signals.append(sig)

    for sig in result.get("sell", []):
        sym = sig.get("symbol", "").upper()
        if sym:
            sig["symbol"] = sym
            sig["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            sell_signals.append(sig)

    for sig in result.get("watch", []):
        sym = sig.get("symbol", "").upper()
        if sym:
            sig["symbol"] = sym
            watch_list.append(sig)

    seen_ids.update(str(m.get("msg_id", "")) for m in new_msgs)
    seen_list = list(seen_ids)[-500:]

    output = {
        "last_analysis": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "buy": buy_signals[-50:],
        "sell": sell_signals[-50:],
        "watch": watch_list[-30:],
        "_seen_ids": seen_list,
    }
    AI_ANALYSIS_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=1))

    buy_count = len(result.get("buy", []))
    sell_count = len(result.get("sell", []))
    if buy_count or sell_count:
        log(f"AI: {buy_count} شراء, {sell_count} بيع")
        for s in result.get("buy", []):
            log(f"  🟢 {s.get('symbol')} [{s.get('confidence')}]: {s.get('reason','')}")
        for s in result.get("sell", []):
            log(f"  🔴 {s.get('symbol')} [{s.get('confidence')}]: {s.get('reason','')}")


def main():
    if "--report" in sys.argv:
        state = load_state()
        report = build_health_report(state)
        log(report.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
        notify(report)
        return

    if "--once" in sys.argv:
        state = load_state()
        alerts = run_checks(state)
        if alerts:
            msg = "⚠️ <b>تنبيه مراقبة البوت</b>\n\n" + "\n\n".join(alerts)
            log(f"تنبيهات: {len(alerts)}")
            notify(msg)
        else:
            log("لا مشاكل")
        return

    log(f"بدء مراقبة {SERVICE_NAME} | فحص كل {CHECK_INTERVAL}s")
    state = load_state()

    # تجاهل اللوق القديم عند أول تشغيل
    if state.log_offset == 0 and TARGET_LOG.exists():
        state.log_offset = TARGET_LOG.stat().st_size
        save_state(state)
        log(f"بدء من نهاية اللوق (offset={state.log_offset})")

    notify(f"🩺 بدأت مراقبة البوت <b>{SERVICE_NAME}</b>\nفحص كل {CHECK_INTERVAL//60} دقيقة")

    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            run_ai_analysis()
            alerts = run_checks(state)
            if alerts:
                import hashlib
                new_alerts = []
                new_hashes = []
                for a in alerts:
                    h = hashlib.md5(a[:80].encode()).hexdigest()[:12]
                    new_hashes.append(h)
                    if h not in state.last_alert_hashes:
                        new_alerts.append(a)
                state.last_alert_hashes = new_hashes
                save_state(state)
                if new_alerts:
                    msg = "⚠️ <b>تنبيه مراقبة البوت</b>\n\n" + "\n\n".join(new_alerts)
                    log(f"تنبيهات ({len(new_alerts)}): {[a[:40] for a in new_alerts]}")
                    notify(msg)
            else:
                if state.last_alert_hashes:
                    state.last_alert_hashes = []
                    save_state(state)

            today = time.strftime("%Y-%m-%d")
            hour = int(time.strftime("%H"))
            if hour == DAILY_SUMMARY_HOUR and state.last_summary_day != today:
                notify(build_health_report(state))
                state.last_summary_day = today
                save_state(state)
                log("تقرير صحة يومي أُرسل")

        except Exception as e:
            log(f"خطأ في المراقبة: {e}")


if __name__ == "__main__":
    main()
