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
import hashlib, hmac, json, os, re, subprocess, sys, time, threading
import urllib.request as _urllib_req
from dataclasses import dataclass, field, asdict
from decimal import Decimal
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
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
BYBIT_KEY = os.getenv("BYBIT_API_KEY", "")
BYBIT_SECRET = os.getenv("BYBIT_API_SECRET", "")
GATE_KEY = os.getenv("GATE_API_KEY", "")
GATE_SECRET = os.getenv("GATE_API_SECRET", "")
KUCOIN_KEY = os.getenv("KUCOIN_API_KEY", "")
KUCOIN_SECRET = os.getenv("KUCOIN_API_SECRET", "")
KUCOIN_PASS = os.getenv("KUCOIN_PASSPHRASE", "")

RAW_MSGS_FILE = BASE_DIR / "channel_raw_messages.json"
AI_ANALYSIS_FILE = BASE_DIR / "ai_channel_analysis.json"

# State files for all trading bots — used to cross-check held coins vs AI
MONTHLY_STATE = BASE_DIR / "monthly_state.json"
DAYTRADING_STATE = BASE_DIR / "daytrading_state.json"
CHANNEL_DT_STATE = BASE_DIR / "channel_daytrader_state.json"
PORTFOLIO_STATE = BASE_DIR / "portfolio_state.json"

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
    info = {"active": False, "restarts": 0, "sub": "?", "since": "?", "masked": False}
    try:
        out = subprocess.run(
            ["systemctl", "show", SERVICE_NAME,
             "-p", "ActiveState,SubState,NRestarts,ActiveEnterTimestamp,LoadState,UnitFileState"],
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
            elif k in ("LoadState", "UnitFileState"):
                # masked / not-found ⇒ الخدمة موقوفة عمداً، لا نراقبها ولا نعيد تشغيلها
                if v in ("masked", "not-found"):
                    info["masked"] = True
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
    """إعادة تشغيل البوت تلقائياً وإرجاع True فقط إذا نجح الأمر فعلاً"""
    try:
        res = subprocess.run(["systemctl", "restart", SERVICE_NAME],
                             capture_output=True, text=True, timeout=30)
        if res.returncode == 0:
            log(f"✅ إعادة تشغيل تلقائية: {reason}")
            return True
        log(f"❌ فشل إعادة التشغيل (كود {res.returncode}): {res.stderr.strip()}")
        return False
    except Exception as e:
        log(f"❌ فشل إعادة التشغيل: {e}")
        return False


def run_checks(state: MonitorState, send_ok: bool = False) -> list[str]:
    """تشغيل كل الفحوصات وإرجاع قائمة التنبيهات"""
    alerts = []

    # 1) حالة الخدمة
    svc = service_status()
    # الخدمة masked/not-found ⇒ موقوفة عمداً (نديرها عبر nohup + watchdog)،
    # فلا ننبّه ولا نحاول إعادة تشغيلها — لكن تحليل الـ AI يستمر كالمعتاد.
    if svc.get("masked"):
        return alerts
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

_cerebras_model = ""
_UA = "Mozilla/5.0 (X11; Linux x86_64) bot-monitor/1.0"


def _cerebras_get_model() -> str:
    """Model names change over time — discover what this key can access."""
    global _cerebras_model
    if _cerebras_model:
        return _cerebras_model
    import urllib.request as req
    try:
        r = req.Request("https://api.cerebras.ai/v1/models",
                        headers={"Authorization": f"Bearer {CEREBRAS_KEY}",
                                 "User-Agent": _UA})
        with req.urlopen(r, timeout=15) as resp:
            ids = [m.get("id", "") for m in json.loads(resp.read()).get("data", [])]
        for pref in ("llama-3.3-70b", "llama3.3-70b", "qwen-3-235b",
                     "gpt-oss", "qwen-3-32b", "llama3.1-8b", "llama"):
            for mid in ids:
                if pref in mid:
                    _cerebras_model = mid
                    log(f"Cerebras model selected: {mid}")
                    return mid
        if ids:
            _cerebras_model = ids[0]
            log(f"Cerebras model selected: {ids[0]}")
            return ids[0]
        log(f"Cerebras: no models available for this key")
    except Exception as e:
        log(f"Cerebras models list error: {e}")
    return "llama-3.3-70b"


def _cerebras_analyze(messages_text: str) -> dict | None:
    if not CEREBRAS_KEY:
        return None
    import urllib.request as req
    prompt = _AI_PROMPT + "الرسائل:\n" + messages_text
    body = json.dumps({
        "model": _cerebras_get_model(),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 8000,
    })
    try:
        r = req.Request("https://api.cerebras.ai/v1/chat/completions",
                        data=body.encode(),
                        headers={"Content-Type": "application/json",
                                 "Authorization": f"Bearer {CEREBRAS_KEY}",
                                 "User-Agent": _UA})
        with req.urlopen(r, timeout=60) as resp:
            data = json.loads(resp.read())
        choices = data.get("choices") or []
        if not choices:
            log(f"Cerebras: empty choices — {json.dumps(data)[:300]}")
            return None
        msg = choices[0].get("message") or choices[0].get("delta") or {}
        content = (msg.get("content") or "").strip() or (msg.get("text") or "").strip() or (msg.get("reasoning") or "").strip()
        if not content:
            log(f"Cerebras: no content — {json.dumps(choices[0])[:300]}")
            return None
        result = _extract_json(content)
        if result:
            log("Cerebras AI analysis OK")
            return result
        log(f"Cerebras: no JSON — {content[:300]}")
    except Exception as e:
        detail = ""
        if hasattr(e, "read"):
            try:
                detail = " | " + e.read().decode()[:300]
            except Exception:
                pass
        if "model_not_found" in str(detail):
            global _cerebras_model
            _cerebras_model = ""
        log(f"Cerebras AI error: {e}{detail}")
    return None


_AI_PROMPT = (
    "أنت محلل عملات رقمية محترف. حلل رسائل القنوات التالية واستخرج:\n"
    "1. أي عملة مذكورة بإيجابية (شراء/صعود/بول ران/بامب/اختراق/فرصة/أي توصية إيجابية)\n"
    "2. أي عملة مذكورة بسلبية (بيع/هبوط/دامب/تحذير)\n"
    "3. مستوى الثقة (high/medium/low)\n\n"
    "افهم المصطلحات المعرّبة: بول ران=bull run, بامب=pump, بريك اوت=breakout, "
    "لونق=long, شورت=short, دامب=dump, تارقت=target, ستوب لوس=stop loss, "
    "هودل=HODL, رالي=rally, مون=moon, سبورت=support, ريزستنس=resistance, "
    "تريند=trend, بيرش=bearish, بولش=bullish, اكيوميوليت=accumulate, "
    "دي سي ايه=DCA, ريكفري=recovery\n\n"
    "عند التوصية بالبيع، حدد نسبة البيع الموصى بها (sell_pct) كرقم 1-100.\n"
    "مثلاً: بيع 50% من الكمية المحتفظ بها، أو بيع 100% (إغلاق كامل).\n\n"
    "أجب بـ JSON فقط بهذا الشكل:\n"
    '{"buy":[{"symbol":"XRP","confidence":"high","reason":"بول ران + اختراق"}],'
    '"sell":[{"symbol":"BTC","confidence":"medium","reason":"هبوط","sell_pct":50}],'
    '"watch":[{"symbol":"ETH","note":"ذكر بدون توصية واضحة"}]}\n\n'
)


def _extract_json(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return None


def _gemini_analyze(messages_text: str) -> dict | None:
    if not GEMINI_KEY:
        return None
    import urllib.request as req
    prompt = _AI_PROMPT + "الرسائل:\n" + messages_text
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2000},
    })
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
    try:
        r = req.Request(url, data=body.encode(),
                        headers={"Content-Type": "application/json",
                                 "User-Agent": _UA})
        with req.urlopen(r, timeout=30) as resp:
            data = json.loads(resp.read())
        candidates = data.get("candidates") or []
        if not candidates:
            log(f"Gemini: no candidates — {json.dumps(data)[:300]}")
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        text = parts[0].get("text", "") if parts else ""
        if not text:
            log(f"Gemini: empty response — {json.dumps(candidates[0])[:300]}")
            return None
        result = _extract_json(text)
        if result:
            log("Gemini AI analysis OK")
            return result
        log(f"Gemini: no JSON — {text[:300]}")
    except Exception as e:
        detail = ""
        if hasattr(e, "read"):
            try:
                detail = " | " + e.read().decode()[:300]
            except Exception:
                pass
        log(f"Gemini AI error: {e}{detail}")
    return None


def run_ai_analysis():
    global _ai_last_run
    now = time.time()
    if now - _ai_last_run < _AI_INTERVAL:
        return
    _ai_last_run = now

    if not (CEREBRAS_KEY or GEMINI_KEY) or not RAW_MSGS_FILE.exists():
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
        result = _gemini_analyze(batch_text)
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
        if sym and not any(s.get("symbol") == sym for s in sell_signals[-20:]):
            sig["symbol"] = sym
            sig["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            sell_signals.append(sig)
    # Expire sell signals older than 24h so a single stale AI SELL
    # doesn't permanently veto a coin in channel_daytrader.
    cutoff = time.time() - 86400
    sell_signals = [s for s in sell_signals
                    if time.mktime(time.strptime(s.get("ts", "2000-01-01T00:00:00"),
                       "%Y-%m-%dT%H:%M:%S")) > cutoff]

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
    _tmp = AI_ANALYSIS_FILE.with_suffix(".tmp")
    _tmp.write_text(json.dumps(output, ensure_ascii=False, indent=1))
    os.replace(_tmp, AI_ANALYSIS_FILE)

    buy_count = len(result.get("buy", []))
    sell_count = len(result.get("sell", []))
    if buy_count or sell_count:
        log(f"AI: {buy_count} شراء, {sell_count} بيع")
        for s in result.get("buy", []):
            log(f"  🟢 {s.get('symbol')} [{s.get('confidence')}]: {s.get('reason','')}")
        for s in result.get("sell", []):
            log(f"  🔴 {s.get('symbol')} [{s.get('confidence')}]: {s.get('reason','')}")


def _normalize_sym(s: str) -> str:
    return s.upper().replace("USDT", "").replace("/", "").strip()


def get_all_held_coins() -> dict[str, list[str]]:
    """Return {symbol: [bot_names]} for every coin currently held across all bots."""
    held: dict[str, list[str]] = {}

    # monthly_channel_bot — open_positions keyed by "SYM/USDT"
    if MONTHLY_STATE.exists():
        try:
            data = json.loads(MONTHLY_STATE.read_text())
            for pair in data.get("open_positions", {}):
                sym = _normalize_sym(pair)
                held.setdefault(sym, []).append("monthly")
        except Exception:
            pass

    # daytrading_bot — positions keyed by "SYMUSDT"
    if DAYTRADING_STATE.exists():
        try:
            data = json.loads(DAYTRADING_STATE.read_text())
            for sym_key in data.get("positions", {}):
                sym = _normalize_sym(sym_key)
                held.setdefault(sym, []).append("daytrading")
        except Exception:
            pass

    # channel_daytrader — positions keyed by "SYM"
    if CHANNEL_DT_STATE.exists():
        try:
            data = json.loads(CHANNEL_DT_STATE.read_text())
            for sym_key in data.get("positions", {}):
                sym = _normalize_sym(sym_key)
                held.setdefault(sym, []).append("channel_dt")
        except Exception:
            pass

    return held


def get_all_positions() -> list[dict]:
    """Return [{symbol, pair, entry, qty, bot, opened_str}, ...] from all bots."""
    positions = []

    if MONTHLY_STATE.exists():
        try:
            data = json.loads(MONTHLY_STATE.read_text())
            for pair, pos in data.get("open_positions", {}).items():
                positions.append({
                    "symbol": _normalize_sym(pair),
                    "pair": pair.replace("/", ""),
                    "entry": pos.get("entry", 0),
                    "qty": pos.get("qty", 0),
                    "bot": "monthly",
                    "opened": pos.get("opened_str", ""),
                })
        except Exception:
            pass

    if DAYTRADING_STATE.exists():
        try:
            data = json.loads(DAYTRADING_STATE.read_text())
            for sym_key, pos in data.get("positions", {}).items():
                positions.append({
                    "symbol": _normalize_sym(sym_key),
                    "pair": sym_key if "USDT" in sym_key else sym_key + "USDT",
                    "entry": pos.get("entry_price", 0),
                    "qty": pos.get("qty", 0),
                    "bot": "daytrading",
                    "opened": pos.get("opened_at", ""),
                })
        except Exception:
            pass

    if CHANNEL_DT_STATE.exists():
        try:
            data = json.loads(CHANNEL_DT_STATE.read_text())
            for sym_key, pos in data.get("positions", {}).items():
                positions.append({
                    "symbol": _normalize_sym(sym_key),
                    "pair": sym_key + "USDT" if "USDT" not in sym_key else sym_key,
                    "entry": pos.get("entry_price", 0),
                    "qty": pos.get("qty", 0),
                    "bot": "channel_dt",
                    "opened": pos.get("opened_at", ""),
                })
        except Exception:
            pass

    return positions


def check_held_vs_ai() -> list[str]:
    """Cross-check every held coin against AI sell recommendations.

    Returns a list of Telegram alert strings for coins the AI flags as SELL.
    """
    if not AI_ANALYSIS_FILE.exists():
        return []
    try:
        ai = json.loads(AI_ANALYSIS_FILE.read_text())
    except Exception:
        return []

    sell_list = ai.get("sell", [])
    if not sell_list:
        return []

    sell_syms = {}
    for s in sell_list:
        sym = _normalize_sym(s.get("symbol", ""))
        if sym:
            sell_syms[sym] = {
                "confidence": s.get("confidence", ""),
                "reason": s.get("reason", ""),
                "sell_pct": s.get("sell_pct", 100),
                "ts": s.get("ts", ""),
            }

    held = get_all_held_coins()
    if not held:
        return []

    alerts = []
    for sym, bots in held.items():
        if sym in sell_syms:
            info = sell_syms[sym]
            bots_str = " + ".join(bots)
            pct = info["sell_pct"]
            pct_label = f"بيع {pct}%" if pct < 100 else "بيع كامل"
            alerts.append(
                f"🔴 <b>توصية بيع: {sym}USDT ({pct_label})</b>\n"
                f"البوتات المحتفظة: {bots_str}\n"
                f"الثقة: {info['confidence']}\n"
                f"السبب: {info['reason']}\n"
                f"التحليل: {info['ts']}"
            )
            log(f"⚠️ AI يوصي ببيع {pct}% من {sym} — محتفظ في: {bots_str}")

    # Also report coins NOT in AI at all (neither buy nor sell)
    buy_syms = {_normalize_sym(s.get("symbol", "")) for s in ai.get("buy", [])}
    for sym, bots in held.items():
        if sym not in sell_syms and sym not in buy_syms:
            alerts.append(
                f"⚪ <b>{sym}USDT</b> — بدون تحليل AI\n"
                f"البوتات: {' + '.join(bots)}"
            )

    return alerts


# ══════════════════════════════════════════════════════════════
# BYBIT TRADING FUNCTIONS (for Telegram command execution)
# ══════════════════════════════════════════════════════════════

def _http_get(url: str, timeout: int = 15) -> dict | None:
    try:
        req = _urllib_req.Request(url, headers={"User-Agent": "bot-monitor/1.0"})
        with _urllib_req.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def _safe_float(val, default=0.0) -> float:
    if not val or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _bybit_signed_get(path: str, params: str) -> dict | None:
    ts = str(int(time.time() * 1000))
    recv = "5000"
    sign_str = f"{ts}{BYBIT_KEY}{recv}{params}"
    sig = hmac.new(BYBIT_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    url = f"https://api.bybit.com{path}?{params}"
    try:
        req = _urllib_req.Request(url, headers={
            "X-BAPI-API-KEY": BYBIT_KEY,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": recv,
            "X-BAPI-SIGN": sig,
        })
        with _urllib_req.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"Bybit GET {path}: {e}")
        return None


def _bybit_signed_post(params: dict) -> dict | None:
    ts = str(int(time.time() * 1000))
    recv = "5000"
    body = json.dumps(params)
    sign_str = f"{ts}{BYBIT_KEY}{recv}{body}"
    sig = hmac.new(BYBIT_SECRET.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    url = "https://api.bybit.com/v5/order/create"
    try:
        req = _urllib_req.Request(url, data=body.encode(), headers={
            "Content-Type": "application/json",
            "X-BAPI-API-KEY": BYBIT_KEY,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": recv,
            "X-BAPI-SIGN": sig,
        }, method="POST")
        with _urllib_req.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"Bybit POST: {e}")
        return None


def _get_lot_step(symbol: str) -> float:
    data = _http_get(f"https://api.bybit.com/v5/market/instruments-info?category=spot&symbol={symbol}")
    if data and data.get("retCode") == 0:
        items = data.get("result", {}).get("list", [])
        if items:
            step = items[0].get("lotSizeFilter", {}).get("basePrecision", "")
            if step:
                try:
                    return float(step)
                except ValueError:
                    pass
    return 0.01


def _round_qty(qty: float, step: float) -> float:
    d_step = Decimal(str(step))
    return float((Decimal(str(qty)) // d_step) * d_step)


def _qty_str(qty: float) -> str:
    s = format(Decimal(str(qty)), 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s


def _fetch_price(symbol: str) -> float | None:
    data = _http_get(f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}")
    if data and data.get("retCode") == 0:
        tickers = data.get("result", {}).get("list", [])
        if tickers:
            val = tickers[0].get("lastPrice", "")
            if val:
                try:
                    return float(val)
                except ValueError:
                    pass
    return None


def _fetch_coin_balance(coin: str) -> float:
    coin = coin.upper().replace("USDT", "")
    data = _bybit_signed_get("/v5/account/wallet-balance", "accountType=UNIFIED")
    if not data or data.get("retCode") != 0:
        return 0.0
    coins = data.get("result", {}).get("list", [{}])[0].get("coin", [])
    for c in coins:
        if c.get("coin") == coin:
            for fld in ("availableToWithdraw", "free", "walletBalance"):
                val = _safe_float(c.get(fld))
                if val > 0:
                    return val
            return 0.0
    return 0.0


def _fetch_usdt_balance() -> float:
    data = _bybit_signed_get("/v5/account/wallet-balance", "accountType=UNIFIED")
    if not data or data.get("retCode") != 0:
        return 0.0
    coins = data.get("result", {}).get("list", [{}])[0].get("coin", [])
    for c in coins:
        if c.get("coin") == "USDT":
            for fld in ("availableToWithdraw", "walletBalance", "equity"):
                val = _safe_float(c.get(fld))
                if val > 0:
                    return val
            return 0.0
    return 0.0


def _fetch_gate_price(symbol: str) -> float | None:
    pair = f"{symbol.upper()}_USDT"
    data = _http_get(f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={pair}")
    if data and isinstance(data, list) and data:
        try:
            return float(data[0].get("last", 0))
        except (ValueError, KeyError):
            pass
    return None


def _gate_signed_get(path: str) -> list | dict | None:
    """Gate.io v4 API signed GET request."""
    if not GATE_KEY or not GATE_SECRET:
        return None
    if "?" in path:
        url_path, query_string = path.split("?", 1)
    else:
        url_path, query_string = path, ""
    ts = str(int(time.time()))
    hashed_body = hashlib.sha512(b"").hexdigest()
    sign_str = f"GET\n{url_path}\n{query_string}\n{hashed_body}\n{ts}"
    sig = hmac.new(GATE_SECRET.encode(), sign_str.encode(), hashlib.sha512).hexdigest()
    url = f"https://api.gateio.ws{path}"
    try:
        req = _urllib_req.Request(url, headers={
            "KEY": GATE_KEY,
            "SIGN": sig,
            "Timestamp": ts,
            "Content-Type": "application/json",
        })
        with _urllib_req.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"Gate GET {path}: {e}")
        return None


def _fetch_gate_usdt() -> float:
    """Fetch Gate.io USDT balance."""
    data = _gate_signed_get("/api/v4/spot/accounts")
    if not data or not isinstance(data, list):
        return 0.0
    for coin in data:
        if coin.get("currency") == "USDT":
            return _safe_float(coin.get("available")) + _safe_float(coin.get("locked"))
    return 0.0


def _fetch_gate_balances() -> list[dict]:
    """Fetch all Gate.io spot balances with value > $1."""
    data = _gate_signed_get("/api/v4/spot/accounts")
    if not data or not isinstance(data, list):
        return []
    result = []
    for coin in data:
        sym = coin.get("currency", "")
        available = _safe_float(coin.get("available"))
        locked = _safe_float(coin.get("locked"))
        total = available + locked
        if total <= 0 or sym in ("USDT", "USD", "USDC"):
            continue
        price = _fetch_gate_price(sym)
        if not price:
            continue
        value = total * price
        if value < 1.0:
            continue
        result.append({"symbol": sym, "amount": total, "price": price, "value": value})
    return result


def _get_gate_holdings_with_entry() -> list[dict]:
    """Gate.io holdings with entry prices from portfolio_state.json + live balances."""
    gate_bals = _fetch_gate_balances()
    entry_prices = {}
    if PORTFOLIO_STATE.exists():
        try:
            pstate = json.loads(PORTFOLIO_STATE.read_text())
            for key, entry in pstate.get("entry_prices", {}).items():
                if "@Gate" in key:
                    sym = key.split("@")[0]
                    entry_prices[sym] = entry
        except Exception:
            pass

    holdings = []
    for b in gate_bals:
        sym = b["symbol"]
        holdings.append({
            "symbol": sym,
            "amount": b["amount"],
            "price": b["price"],
            "value": b["value"],
            "entry": entry_prices.get(sym, 0),
        })
    return holdings


def _fetch_kucoin_price(symbol: str) -> float | None:
    data = _http_get(f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol.upper()}-USDT")
    if data and data.get("code") == "200000":
        price = data.get("data", {}).get("price")
        if price:
            try:
                return float(price)
            except ValueError:
                pass
    return None


def _kucoin_signed_get(path: str) -> dict | None:
    """KuCoin v2 API signed GET request."""
    if not KUCOIN_KEY or not KUCOIN_SECRET:
        return None
    import base64
    ts = str(int(time.time() * 1000))
    sign_str = f"{ts}GET{path}"
    sig = base64.b64encode(
        hmac.new(KUCOIN_SECRET.encode(), sign_str.encode(), hashlib.sha256).digest()
    ).decode()
    passphrase = base64.b64encode(
        hmac.new(KUCOIN_SECRET.encode(), KUCOIN_PASS.encode(), hashlib.sha256).digest()
    ).decode()
    url = f"https://api.kucoin.com{path}"
    try:
        req = _urllib_req.Request(url, headers={
            "KC-API-KEY": KUCOIN_KEY,
            "KC-API-SIGN": sig,
            "KC-API-TIMESTAMP": ts,
            "KC-API-PASSPHRASE": passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json",
        })
        with _urllib_req.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"KuCoin GET {path}: {e}")
        return None


def _fetch_kucoin_balances() -> list[dict]:
    """Fetch KuCoin spot balances with value > $1."""
    data = _kucoin_signed_get("/api/v1/accounts?type=trade")
    if not data or data.get("code") != "200000":
        return []
    result = []
    for acc in data.get("data", []):
        sym = acc.get("currency", "")
        total = _safe_float(acc.get("balance"))
        if total <= 0 or sym in ("USDT", "USD", "USDC"):
            continue
        price = _fetch_kucoin_price(sym)
        if not price:
            continue
        value = total * price
        if value < 1.0:
            continue
        result.append({"symbol": sym, "amount": total, "price": price, "value": value})
    return result


def _get_kucoin_holdings_with_entry() -> list[dict]:
    """KuCoin holdings with entry prices from portfolio_state.json + live balances."""
    kc_bals = _fetch_kucoin_balances()
    entry_prices = {}
    if PORTFOLIO_STATE.exists():
        try:
            pstate = json.loads(PORTFOLIO_STATE.read_text())
            for key, entry in pstate.get("entry_prices", {}).items():
                if "@KuCoin" in key:
                    sym = key.split("@")[0]
                    entry_prices[sym] = entry
        except Exception:
            pass

    holdings = []
    for b in kc_bals:
        sym = b["symbol"]
        holdings.append({
            "symbol": sym,
            "amount": b["amount"],
            "price": b["price"],
            "value": b["value"],
            "entry": entry_prices.get(sym, 0),
        })
    return holdings


def _coin_to_usdt(coin: str, amount: float) -> float:
    """Convert a coin amount to USDT value. Returns 0 if price unavailable."""
    if coin in ("USDT", "USDC", "USD", "BUSD", "DAI"):
        return amount
    price = _fetch_price(f"{coin}USDT") or _fetch_gate_price(coin) or _fetch_kucoin_price(coin)
    return amount * price if price else 0.0


def _fetch_bybit_deposits_withdrawals() -> tuple[float, float]:
    """Fetch total deposits and withdrawals from Bybit (last 6 months)."""
    if not BYBIT_KEY:
        return 0.0, 0.0
    start_ms = str(int((time.time() - 180 * 86400) * 1000))
    end_ms = str(int(time.time() * 1000))

    total_dep = 0.0
    cursor = ""
    for _ in range(20):
        params = f"startTime={start_ms}&endTime={end_ms}&limit=50"
        if cursor:
            params += f"&cursor={cursor}"
        data = _bybit_signed_get("/v5/asset/deposit/query-record", params)
        if not data:
            log("Bybit deposit API: no response")
            break
        if data.get("retCode") != 0:
            log(f"Bybit deposit API: {data.get('retCode')} — {data.get('retMsg', '')}")
            break
        rows = data.get("result", {}).get("rows", [])
        for r in rows:
            status = r.get("status")
            if status in (3, "3", 4, "4", 1, "1", 10000, "10000"):
                total_dep += _coin_to_usdt(r.get("coin", ""), _safe_float(r.get("amount")))
        cursor = data.get("result", {}).get("nextPageCursor", "")
        if not cursor or not rows:
            break
    log(f"Bybit deposits: ${total_dep:,.2f}")

    total_wd = 0.0
    cursor = ""
    for _ in range(20):
        params = f"startTime={start_ms}&endTime={end_ms}&limit=50&withdrawType=2"
        if cursor:
            params += f"&cursor={cursor}"
        data = _bybit_signed_get("/v5/asset/withdraw/query-record", params)
        if not data:
            log("Bybit withdraw API: no response")
            break
        if data.get("retCode") != 0:
            log(f"Bybit withdraw API: {data.get('retCode')} — {data.get('retMsg', '')}")
            break
        rows = data.get("result", {}).get("rows", [])
        for r in rows:
            status = str(r.get("status", ""))
            if status.lower() in ("success", "blockchainconfirmed"):
                total_wd += _coin_to_usdt(r.get("coin", ""), _safe_float(r.get("amount")))
        cursor = data.get("result", {}).get("nextPageCursor", "")
        if not cursor or not rows:
            break
    log(f"Bybit withdrawals: ${total_wd:,.2f}")

    return total_dep, total_wd


def _fetch_gate_deposits_withdrawals() -> tuple[float, float]:
    """Fetch total deposits and withdrawals from Gate.io (last 6 months)."""
    if not GATE_KEY:
        return 0.0, 0.0
    frm = str(int(time.time() - 180 * 86400))
    to = str(int(time.time()))

    total_dep = 0.0
    offset = 0
    for _ in range(10):
        data = _gate_signed_get(f"/api/v4/wallet/deposits?from={frm}&to={to}&limit=100&offset={offset}")
        if not data or not isinstance(data, list):
            break
        for r in data:
            if r.get("status") == "DONE":
                total_dep += _coin_to_usdt(r.get("currency", ""), _safe_float(r.get("amount")))
        if len(data) < 100:
            break
        offset += 100
    log(f"Gate deposits: ${total_dep:,.2f}")

    total_wd = 0.0
    offset = 0
    for _ in range(10):
        data = _gate_signed_get(f"/api/v4/wallet/withdrawals?from={frm}&to={to}&limit=100&offset={offset}")
        if not data or not isinstance(data, list):
            break
        for r in data:
            if r.get("status") == "DONE":
                total_wd += _coin_to_usdt(r.get("currency", ""), _safe_float(r.get("amount")))
        if len(data) < 100:
            break
        offset += 100
    log(f"Gate withdrawals: ${total_wd:,.2f}")

    return total_dep, total_wd


def _fetch_kucoin_deposits_withdrawals() -> tuple[float, float]:
    """Fetch total deposits and withdrawals from KuCoin (last 6 months)."""
    if not KUCOIN_KEY:
        return 0.0, 0.0
    start_at = str(int((time.time() - 180 * 86400) * 1000))
    end_at = str(int(time.time() * 1000))

    total_dep = 0.0
    for page in range(1, 11):
        data = _kucoin_signed_get(
            f"/api/v1/deposits?startAt={start_at}&endAt={end_at}&pageSize=100&currentPage={page}"
        )
        if not data or data.get("code") != "200000":
            break
        items = data.get("data", {}).get("items", [])
        for r in items:
            if r.get("status") == "SUCCESS":
                total_dep += _coin_to_usdt(r.get("currency", ""), _safe_float(r.get("amount")))
        if page >= data.get("data", {}).get("totalPage", 1):
            break

    total_wd = 0.0
    for page in range(1, 11):
        data = _kucoin_signed_get(
            f"/api/v1/withdrawals?startAt={start_at}&endAt={end_at}&pageSize=100&currentPage={page}"
        )
        if not data or data.get("code") != "200000":
            break
        items = data.get("data", {}).get("items", [])
        for r in items:
            if r.get("status") == "SUCCESS":
                total_wd += _coin_to_usdt(r.get("currency", ""), _safe_float(r.get("amount")))
        if page >= data.get("data", {}).get("totalPage", 1):
            break

    return total_dep, total_wd


def _fetch_all_deposits_withdrawals() -> dict:
    """Fetch deposits/withdrawals from all exchanges. Returns summary dict."""
    result = {"exchanges": {}, "total_deposited": 0.0, "total_withdrawn": 0.0}

    for name, fetcher in [("Bybit", _fetch_bybit_deposits_withdrawals),
                          ("Gate.io", _fetch_gate_deposits_withdrawals),
                          ("KuCoin", _fetch_kucoin_deposits_withdrawals)]:
        try:
            dep, wd = fetcher()
            result["exchanges"][name] = {"deposited": dep, "withdrawn": wd}
            result["total_deposited"] += dep
            result["total_withdrawn"] += wd
        except Exception as e:
            log(f"خطأ جلب إيداعات/سحوبات {name}: {e}")
            result["exchanges"][name] = {"deposited": 0, "withdrawn": 0, "error": str(e)}

    return result


def _execute_sell(symbol: str, sell_pct: float) -> str:
    """Execute a sell order. symbol is base coin (e.g. 'ENJ'). sell_pct is 1-100."""
    if not BYBIT_KEY or not BYBIT_SECRET:
        return "❌ مفاتيح Bybit غير متوفرة"

    pair = f"{symbol.upper()}USDT"
    free = _fetch_coin_balance(symbol)
    if free <= 0:
        return f"❌ لا يوجد رصيد من {symbol} في المحفظة"

    price = _fetch_price(pair)
    if not price:
        return f"❌ لم أستطع جلب سعر {pair}"

    sell_qty = free * (sell_pct / 100.0)
    value_usd = sell_qty * price

    if value_usd < 1.0:
        return f"❌ قيمة البيع أقل من $1 ({symbol}: {sell_qty:.6f} ≈ ${value_usd:.2f})"

    step = _get_lot_step(pair)
    sell_qty = _round_qty(sell_qty, step)

    if sell_qty <= 0:
        return f"❌ الكمية صفر بعد التقريب (step={step})"

    result = _bybit_signed_post({
        "category": "spot",
        "symbol": pair,
        "side": "Sell",
        "orderType": "Market",
        "qty": _qty_str(sell_qty),
        "marketUnit": "baseCoin",
    })

    if result and result.get("retCode") == 0:
        actual_value = sell_qty * price
        pct_label = f"{sell_pct:.0f}%"
        msg = (f"✅ تم بيع {pct_label} من {symbol}\n"
               f"الكمية: {_qty_str(sell_qty)}\n"
               f"السعر: ${price:,.6f}\n"
               f"القيمة: ${actual_value:,.2f}\n"
               f"المتبقي: {_qty_str(free - sell_qty)} {symbol}")
        log(f"CMD SELL: {symbol} {pct_label} — qty={sell_qty} @ ${price}")
        return msg

    err_msg = result.get("retMsg", "unknown") if result else "no response"
    err_code = result.get("retCode", "?") if result else "?"
    log(f"CMD SELL FAILED: {symbol} — {err_code}: {err_msg}")
    return f"❌ فشل البيع: {err_code} — {err_msg}"


# ══════════════════════════════════════════════════════════════
# TELEGRAM COMMAND INTERFACE
# ══════════════════════════════════════════════════════════════

_tg_update_offset = 0


def _tg_get_updates() -> list[dict]:
    """Fetch new messages via Telegram Bot API long-polling."""
    global _tg_update_offset
    if not NOTIFY_TOKEN:
        return []
    url = (f"https://api.telegram.org/bot{NOTIFY_TOKEN}/getUpdates"
           f"?offset={_tg_update_offset}&timeout=30&allowed_updates=[\"message\"]")
    try:
        req = _urllib_req.Request(url, headers={"User-Agent": "bot-monitor/1.0"})
        with _urllib_req.urlopen(req, timeout=45) as r:
            data = json.loads(r.read())
        if not data.get("ok"):
            return []
        updates = data.get("result", [])
        if updates:
            _tg_update_offset = updates[-1]["update_id"] + 1
        return updates
    except Exception as e:
        log(f"TG getUpdates: {e}")
        return []


def _handle_command(text: str) -> str | None:
    """Parse and execute a Telegram command. Returns reply text or None."""
    text = text.strip()
    if not text:
        return None

    # ── بيع / sell ──
    sell_match = re.match(
        r"(?:بيع|sell)\s+([A-Za-z]+)\s*(\d+)?\s*%?",
        text, re.IGNORECASE
    )
    if sell_match:
        symbol = sell_match.group(1).upper()
        pct = int(sell_match.group(2)) if sell_match.group(2) else 100
        if pct < 1 or pct > 100:
            return "❌ النسبة يجب أن تكون بين 1 و 100"
        return _execute_sell(symbol, pct)

    # ── مراجعة / review ──
    if text in ("مراجعة", "review", "/review"):
        run_ai_analysis()
        alerts = check_held_vs_ai()
        if alerts:
            return "🔎 <b>مراجعة العملات المحتفظ بها</b>\n\n" + "\n\n".join(alerts)
        return "✅ لا توجد توصيات بيع لأي عملة محتفظ بها"

    # ── حالة / status ──
    if text in ("حالة", "status", "/status"):
        state = load_state()
        return build_health_report(state)

    # ── رصيد / balance ──
    if text in ("رصيد", "balance", "/balance"):
        lines = [f"<b>💰 رصيد المحفظة</b>\n"]
        grand_total = 0.0

        # Bybit
        if BYBIT_KEY:
            usdt = _fetch_usdt_balance()
            held = get_all_held_coins()
            bybit_total = usdt
            lines.append("<b>━━ Bybit ━━</b>")
            lines.append(f"💵 USDT: ${usdt:,.2f}")
            for sym, bots in sorted(held.items()):
                bal = _fetch_coin_balance(sym)
                price = _fetch_price(f"{sym}USDT")
                val = bal * price if (bal and price) else 0
                bybit_total += val
                lines.append(f"{sym}: {_qty_str(bal)} ≈ ${val:,.2f}  ({', '.join(bots)})")
            lines.append(f"<b>Bybit: ${bybit_total:,.2f}</b>")
            grand_total += bybit_total

        # Gate.io
        if GATE_KEY:
            gate_usdt = _fetch_gate_usdt()
            gate_bals = _fetch_gate_balances()
            gate_total = gate_usdt + sum(b["value"] for b in gate_bals)
            lines.append(f"\n<b>━━ Gate.io ━━</b>")
            if gate_usdt >= 1:
                lines.append(f"💵 USDT: ${gate_usdt:,.2f}")
            for b in sorted(gate_bals, key=lambda x: x["value"], reverse=True):
                lines.append(f"{b['symbol']}: {_qty_str(b['amount'])} ≈ ${b['value']:,.2f}")
            lines.append(f"<b>Gate.io: ${gate_total:,.2f}</b>")
            grand_total += gate_total

        # KuCoin
        if KUCOIN_KEY:
            kc_bals = _fetch_kucoin_balances()
            kc_usdt = 0.0
            kc_data = _kucoin_signed_get("/api/v1/accounts?type=trade")
            if kc_data and kc_data.get("code") == "200000":
                for acc in kc_data.get("data", []):
                    if acc.get("currency") == "USDT":
                        kc_usdt = _safe_float(acc.get("balance"))
            kc_total = kc_usdt + sum(b["value"] for b in kc_bals)
            lines.append(f"\n<b>━━ KuCoin ━━</b>")
            if kc_usdt >= 1:
                lines.append(f"💵 USDT: ${kc_usdt:,.2f}")
            for b in sorted(kc_bals, key=lambda x: x["value"], reverse=True):
                lines.append(f"{b['symbol']}: {_qty_str(b['amount'])} ≈ ${b['value']:,.2f}")
            lines.append(f"<b>KuCoin: ${kc_total:,.2f}</b>")
            grand_total += kc_total

        lines.append(f"\n<b>القيمة الحالية: ${grand_total:,.2f}</b>")

        # إيداعات وسحوبات
        dw = _fetch_all_deposits_withdrawals()
        total_dep = dw["total_deposited"]
        total_wd = dw["total_withdrawn"]
        if total_dep > 0 or total_wd > 0:
            net = total_dep - total_wd
            pnl = grand_total + total_wd - total_dep
            pnl_pct = (pnl / total_dep * 100) if total_dep > 0 else 0
            icon = "🟢" if pnl >= 0 else "🔴"
            lines.append(
                f"\n<b>━━ ملخص رأس المال (6 أشهر) ━━</b>\n"
                f"إجمالي الإيداع: ${total_dep:,.2f}"
            )
            for ex, info in dw["exchanges"].items():
                if info["deposited"] > 0 or info["withdrawn"] > 0:
                    lines.append(f"  {ex}: إيداع ${info['deposited']:,.2f} | سحب ${info['withdrawn']:,.2f}")
            lines.append(
                f"إجمالي السحب: ${total_wd:,.2f}\n"
                f"صافي الاستثمار: ${net:,.2f}\n"
                f"{icon} <b>الربح/الخسارة: {pnl_pct:+.2f}% (${pnl:+,.2f})</b>"
            )

        return "\n".join(lines)

    # ── عملات / coins / holdings ──
    if text in ("عملات", "coins", "holdings", "/coins"):
        held = get_all_held_coins()
        if not held:
            return "📭 لا توجد عملات محتفظ بها حالياً"
        lines = ["<b>📊 العملات المحتفظ بها</b>\n"]
        for sym, bots in sorted(held.items()):
            lines.append(f"  {sym}USDT — {', '.join(bots)}")
        return "\n".join(lines)

    # ── أرباح / pnl ──
    if text in ("أرباح", "ارباح", "pnl", "/pnl", "ربح"):
        positions = get_all_positions()
        if not positions and not GATE_KEY:
            return "📭 لا توجد مراكز مفتوحة"
        lines = ["<b>📈 أرباح/خسائر المراكز المفتوحة</b>\n"]
        total_cost = 0.0
        total_value = 0.0

        # ── Bybit bots ──
        if positions:
            lines.append("<b>━━ Bybit ━━</b>")
            for p in sorted(positions, key=lambda x: x["symbol"]):
                entry = p["entry"]
                qty = p["qty"]
                pair = p["pair"]
                if not entry or not qty:
                    lines.append(f"  ⚪ {p['symbol']} ({p['bot']}) — بيانات ناقصة")
                    continue
                price = _fetch_price(pair)
                if not price:
                    lines.append(f"  ⚪ {p['symbol']} ({p['bot']}) — سعر غير متوفر")
                    continue
                cost = entry * qty
                value = price * qty
                pnl_pct = ((price - entry) / entry) * 100
                pnl_usd = value - cost
                total_cost += cost
                total_value += value
                icon = "🟢" if pnl_pct >= 0 else "🔴"
                lines.append(
                    f"  {icon} <b>{p['symbol']}</b> ({p['bot']})\n"
                    f"      دخول: ${entry:,.6f} → حالي: ${price:,.6f}\n"
                    f"      الربح: {pnl_pct:+.2f}% (${pnl_usd:+,.2f})"
                )

        # ── Gate.io ──
        if GATE_KEY:
            gate_holdings = _get_gate_holdings_with_entry()
            if gate_holdings:
                lines.append("\n<b>━━ Gate.io ━━</b>")
                gate_cost = 0.0
                gate_value = 0.0
                for h in sorted(gate_holdings, key=lambda x: x["symbol"]):
                    sym = h["symbol"]
                    entry = h["entry"]
                    price = h["price"]
                    amount = h["amount"]
                    value = h["value"]
                    if entry and entry > 0:
                        pnl_pct = ((price - entry) / entry) * 100
                        pnl_usd = (price - entry) * amount
                        icon = "🟢" if pnl_pct >= 0 else "🔴"
                        gate_cost += entry * amount
                        gate_value += value
                        lines.append(
                            f"  {icon} <b>{sym}</b>\n"
                            f"      دخول: ${entry:,.6f} → حالي: ${price:,.6f}\n"
                            f"      الربح: {pnl_pct:+.2f}% (${pnl_usd:+,.2f})"
                        )
                    else:
                        lines.append(
                            f"  ⚪ <b>{sym}</b>: ${price:,.6f} × {_qty_str(amount)} = ${value:,.2f}\n"
                            f"      سعر الدخول غير متوفر"
                        )
                if gate_cost > 0:
                    g_pnl_pct = ((gate_value - gate_cost) / gate_cost) * 100
                    g_pnl_usd = gate_value - gate_cost
                    lines.append(f"  <b>Gate.io: {g_pnl_pct:+.2f}% (${g_pnl_usd:+,.2f})</b>")

        # ── KuCoin ──
        if KUCOIN_KEY:
            kc_holdings = _get_kucoin_holdings_with_entry()
            if kc_holdings:
                lines.append("\n<b>━━ KuCoin ━━</b>")
                kc_cost = 0.0
                kc_value = 0.0
                for h in sorted(kc_holdings, key=lambda x: x["symbol"]):
                    sym = h["symbol"]
                    entry = h["entry"]
                    price = h["price"]
                    amount = h["amount"]
                    value = h["value"]
                    if entry and entry > 0:
                        pnl_pct = ((price - entry) / entry) * 100
                        pnl_usd = (price - entry) * amount
                        icon = "🟢" if pnl_pct >= 0 else "🔴"
                        kc_cost += entry * amount
                        kc_value += value
                        lines.append(
                            f"  {icon} <b>{sym}</b>\n"
                            f"      دخول: ${entry:,.6f} → حالي: ${price:,.6f}\n"
                            f"      الربح: {pnl_pct:+.2f}% (${pnl_usd:+,.2f})"
                        )
                    else:
                        lines.append(
                            f"  ⚪ <b>{sym}</b>: ${price:,.6f} × {_qty_str(amount)} = ${value:,.2f}\n"
                            f"      سعر الدخول غير متوفر"
                        )
                if kc_cost > 0:
                    k_pnl_pct = ((kc_value - kc_cost) / kc_cost) * 100
                    k_pnl_usd = kc_value - kc_cost
                    lines.append(f"  <b>KuCoin: {k_pnl_pct:+.2f}% (${k_pnl_usd:+,.2f})</b>")

        if total_cost > 0:
            total_pnl_pct = ((total_value - total_cost) / total_cost) * 100
            total_pnl_usd = total_value - total_cost
            lines.append(f"\n<b>إجمالي Bybit: {total_pnl_pct:+.2f}% (${total_pnl_usd:+,.2f})</b>")

        # ── الربح الإجمالي من رأس المال ──
        dw = _fetch_all_deposits_withdrawals()
        deposited = dw["total_deposited"]
        withdrawn = dw["total_withdrawn"]
        if deposited > 0:
            portfolio_value = 0.0
            if BYBIT_KEY:
                portfolio_value += _fetch_usdt_balance()
                for sym, _ in get_all_held_coins().items():
                    bal = _fetch_coin_balance(sym)
                    price = _fetch_price(f"{sym}USDT")
                    if bal and price:
                        portfolio_value += bal * price
            if GATE_KEY:
                for b in _fetch_gate_balances():
                    portfolio_value += b["value"]
            if KUCOIN_KEY:
                for b in _fetch_kucoin_balances():
                    portfolio_value += b["value"]

            net = deposited - withdrawn
            overall_pnl = portfolio_value + withdrawn - deposited
            overall_pct = (overall_pnl / deposited) * 100
            icon = "🟢" if overall_pnl >= 0 else "🔴"
            lines.append(
                f"\n{icon} <b>━━ الربح الإجمالي (6 أشهر) ━━</b>\n"
                f"إجمالي الإيداع: ${deposited:,.2f}\n"
                f"إجمالي السحب: ${withdrawn:,.2f}\n"
                f"صافي الاستثمار: ${net:,.2f}\n"
                f"القيمة الحالية: ${portfolio_value:,.2f}\n"
                f"<b>الربح/الخسارة: {overall_pct:+.2f}% (${overall_pnl:+,.2f})</b>"
            )

        return "\n".join(lines)

    # ── أوامر / help ──
    if text in ("أوامر", "help", "/help", "مساعدة"):
        return (
            "<b>📋 الأوامر المتاحة:</b>\n\n"
            "<b>تداول:</b>\n"
            "<code>بيع ENJ 50%</code> — بيع 50% من ENJ\n"
            "<code>بيع ENJ</code> — بيع 100%\n\n"
            "<b>محفظة:</b>\n"
            "<code>أرباح</code> — ربح/خسارة كل عملة + إجمالي\n"
            "<code>رصيد</code> — رصيد + إيداعات/سحوبات كل المنصات\n"
            "<code>عملات</code> — العملات المحتفظ بها\n\n"
            "<b>أخرى:</b>\n"
            "<code>مراجعة</code> — مراجعة AI للعملات\n"
            "<code>حالة</code> — تقرير صحة البوتات\n"
            "<code>أوامر</code> — هذه القائمة"
        )

    return None


def _tg_reply(chat_id: str, text: str):
    """Send a reply to a specific chat."""
    if not NOTIFY_TOKEN:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{NOTIFY_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        log(f"TG reply error: {e}")


def _command_loop():
    """Background thread: poll Telegram for commands and execute them."""
    global _tg_update_offset
    # Skip old messages on startup
    log("CMD: بدء واجهة أوامر تيليجرام...")
    try:
        boot = _tg_get_updates()
        if boot:
            log(f"CMD: تخطي {len(boot)} رسالة قديمة")
    except Exception:
        pass

    while True:
        try:
            updates = _tg_get_updates()
            for upd in updates:
                msg = upd.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "")

                if chat_id != NOTIFY_CHAT:
                    continue

                reply = _handle_command(text)
                if reply:
                    _tg_reply(chat_id, reply)
        except Exception as e:
            log(f"CMD loop error: {e}")
            time.sleep(10)


def main():
    if "--report" in sys.argv:
        state = load_state()
        report = build_health_report(state)
        log(report.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
        notify(report)
        return

    if "--review" in sys.argv:
        run_ai_analysis()
        alerts = check_held_vs_ai()
        if alerts:
            msg = "🔎 <b>مراجعة العملات المحتفظ بها</b>\n\n" + "\n\n".join(alerts)
            log(msg.replace("<b>", "").replace("</b>", ""))
            notify(msg)
        else:
            msg = "✅ لا توجد توصيات بيع لأي عملة محتفظ بها"
            log(msg)
            notify(msg)
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

    notify(f"🩺 بدأت مراقبة البوت <b>{SERVICE_NAME}</b>\nفحص كل {CHECK_INTERVAL//60} دقيقة\n📱 واجهة الأوامر فعّالة — أرسل <code>أوامر</code> لعرض القائمة")

    cmd_thread = threading.Thread(target=_command_loop, daemon=True)
    cmd_thread.start()

    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            run_ai_analysis()
            # Cross-check held coins against AI sell recommendations
            held_alerts = check_held_vs_ai()
            if held_alerts:
                sell_only = [a for a in held_alerts if "توصية بيع" in a]
                if sell_only:
                    msg = "🔎 <b>تنبيه: AI يوصي ببيع عملات محتفظ بها</b>\n\n" + "\n\n".join(sell_only)
                    notify(msg)
            alerts = run_checks(state)
            if alerts:
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
