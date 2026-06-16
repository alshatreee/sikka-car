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
import fcntl, hashlib, hmac, json, os, re, subprocess, sys, time, threading
import secrets as _secrets
import urllib.request as _urllib_req
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(r"C:\Users\xman9\Desktop") if os.name == "nt" else Path("/root/bots")
BASE_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = BASE_DIR / ".env_monthly"
TARGET_LOG = BASE_DIR / "monthly.log"
SMART_LOG = BASE_DIR / "smart_channel_bot.log"
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

# State files for active trading bots — used to cross-check held coins vs AI
MONTHLY_STATE = BASE_DIR / "monthly_state.json"
SMART_STATE = BASE_DIR / "smart_state.json"
PORTFOLIO_STATE = BASE_DIR / "portfolio_state.json"
CAPITAL_CONFIG = BASE_DIR / "capital_config.json"

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
    smart_log_offset: int = 0
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
    """قراءة الأسطر الجديدة من لوقات البوتات منذ آخر فحص"""
    all_lines = []
    for log_path, attr in ((TARGET_LOG, "log_offset"), (SMART_LOG, "smart_log_offset")):
        if not log_path.exists():
            continue
        size = log_path.stat().st_size
        offset = getattr(state, attr)
        if offset > size:
            offset = 0
        with log_path.open("r", errors="replace") as f:
            f.seek(offset)
            all_lines.extend(f.readlines())
            setattr(state, attr, f.tell())
    return all_lines


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

    # 1) حالة البوتات (nohup + watchdog)
    for bot_name in ("monthly_channel_bot", "smart_channel_bot"):
        if not _process_alive(bot_name):
            alerts.append(
                f"🔴 <b>{bot_name} متوقف!</b>\n"
                f"الحل: الـ watchdog سيعيد تشغيله خلال 5 دقائق"
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


def _process_alive(name: str) -> bool:
    try:
        r = subprocess.run(["pgrep", "-fc", f"python3 {name}.py --live"],
                           capture_output=True, text=True, timeout=5)
        return r.returncode == 0 and int(r.stdout.strip() or "0") > 0
    except Exception:
        return False


def _log_age(path: Path) -> float:
    if not path.exists():
        return 1e9
    return (time.time() - path.stat().st_mtime) / 60


def build_health_report(state: MonitorState) -> str:
    bots_info = [
        ("monthly_channel_bot", BASE_DIR / "monthly.log"),
        ("smart_channel_bot", BASE_DIR / "smart_channel_bot.log"),
    ]
    lines = ["<b>🩺 تقرير صحة البوتات</b>\n"]
    for bot_name, log_path in bots_info:
        alive = _process_alive(bot_name)
        status = "🟢 شغّال" if alive else "🔴 متوقف"
        age = _log_age(log_path)
        lines.append(f"<b>{bot_name}</b>: {status}")
        lines.append(f"  آخر تحديث لوق: قبل {age:.0f} دقيقة")
    lines.append("")
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
        err_msg = str(e).replace(GEMINI_KEY, "***") if GEMINI_KEY else str(e)
        log(f"Gemini AI error: {err_msg}{detail}")
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
    def _ts_ok(s) -> bool:
        try:
            return time.mktime(time.strptime(s.get("ts", ""), "%Y-%m-%dT%H:%M:%S")) > cutoff
        except (ValueError, TypeError):
            return False  # malformed ts → treat as expired, never crash analysis
    sell_signals = [s for s in sell_signals if _ts_ok(s)]

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

    # smart_channel_bot — open_positions keyed by "SYM/USDT"
    if SMART_STATE.exists():
        try:
            data = json.loads(SMART_STATE.read_text())
            for pair in data.get("open_positions", {}):
                sym = _normalize_sym(pair)
                held.setdefault(sym, []).append("smart")
        except Exception:
            pass

    return held


def real_held_symbols() -> set[str]:
    """Symbols actually present in any exchange wallet (value > $1).
    Used to filter out phantom positions left in bot state files."""
    syms: set[str] = set()
    try:
        if BYBIT_KEY:
            for h in _get_bybit_holdings_with_entry():
                syms.add(h["symbol"].upper())
    except Exception:
        pass
    try:
        if GATE_KEY:
            for h in _fetch_gate_balances():
                syms.add(h["symbol"].upper())
    except Exception:
        pass
    try:
        if KUCOIN_KEY:
            for h in _fetch_kucoin_balances():
                syms.add(h["symbol"].upper())
    except Exception:
        pass
    return syms


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

    if SMART_STATE.exists():
        try:
            data = json.loads(SMART_STATE.read_text())
            for pair, pos in data.get("open_positions", {}).items():
                positions.append({
                    "symbol": _normalize_sym(pair),
                    "pair": pair.replace("/", ""),
                    "entry": pos.get("entry", 0),
                    "qty": pos.get("qty", 0),
                    "bot": "smart",
                    "opened": pos.get("opened_str", ""),
                })
        except Exception:
            pass

    return positions


_DAY_BOTS = {"smart"}


def check_held_vs_ai() -> list[str]:
    """Cross-check every held coin against AI sell recommendations.

    Day-trading bots consume AI sells themselves and close their own positions,
    so bot_monitor only ALERTS — and only for coins held outside those bots
    (monthly / manual holdings). It never auto-executes.
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

    # only alert for coins actually in a wallet — skip phantom positions that
    # linger in a bot's state file after the coin was already sold
    real = real_held_symbols()

    alerts = []
    for sym, bots in held.items():
        if sym not in sell_syms:
            continue
        if real and sym not in real:
            log(f"AI يوصي ببيع {sym} — لكنها غير موجودة بالمحفظة (تجاهل)")
            continue
        info = sell_syms[sym]
        bots_str = " + ".join(bots)
        pct = info["sell_pct"]
        pct_label = f"بيع {pct}%" if pct < 100 else "بيع كامل"
        day_bots = [b for b in bots if b in _DAY_BOTS]

        if day_bots:
            # Day-trading bots consume the AI sell signal themselves and close
            # their OWN positions (so their state stays consistent). bot_monitor
            # must NOT execute here — selling out from under a bot would desync
            # its position records. Stay silent; the bot sends its own CLOSE.
            log(f"AI يوصي ببيع {sym} — متروك لبوت التداول ({', '.join(day_bots)})")
            continue

        # Held only outside the day-trading bots (monthly / manual) → alert,
        # user decides. AI never auto-executes on these.
        alerts.append(
            f"🔴 <b>توصية بيع: {sym}USDT ({pct_label})</b>\n"
            f"البوتات المحتفظة: {bots_str}\n"
            f"الثقة: {info['confidence']}\n"
            f"السبب: {info['reason']}\n"
            f"💡 أرسل <code>بيع {sym}</code> للتنفيذ اليدوي"
        )
        log(f"⚠️ AI يوصي ببيع {sym} — تنبيه بدون تنفيذ (محفظة غير مُدارة)")

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
    # Idempotency: a client order id lets us look the order up later if the
    # response is lost, and lets the exchange reject an accidental duplicate.
    params = dict(params)
    params.setdefault("orderLinkId", f"mon{int(time.time()*1000)}{_secrets.token_hex(3)}")
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
        # The request may have reached Bybit and executed even though we never
        # got the reply (e.g. read timeout). NEVER report this as a clean
        # failure — a blind retry would double-sell. Surface it as ambiguous.
        log(f"Bybit POST AMBIGUOUS (order may have executed): {e}")
        return {"retCode": -999, "retMsg": "network error", "_ambiguous": True,
                "orderLinkId": params.get("orderLinkId", "")}


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
    total = 0.0
    # UNIFIED account (trading)
    data = _bybit_signed_get("/v5/account/wallet-balance", "accountType=UNIFIED")
    if data and data.get("retCode") == 0:
        for c in data.get("result", {}).get("list", [{}])[0].get("coin", []):
            if c.get("coin") == coin:
                total += _safe_float(c.get("availableToWithdraw")) or _safe_float(c.get("free"))
    # Funding account (deposits, earn, etc.)
    fund = _bybit_signed_get("/v5/asset/transfer/query-asset-info", f"coin={coin}")
    if fund and fund.get("retCode") == 0:
        for item in fund.get("result", {}).get("list", []):
            if item.get("coin") == coin:
                total += _safe_float(item.get("availableToWithdraw"))
    return total


def _fetch_usdt_balance() -> float:
    total = 0.0
    # UNIFIED account
    data = _bybit_signed_get("/v5/account/wallet-balance", "accountType=UNIFIED")
    if data and data.get("retCode") == 0:
        for c in data.get("result", {}).get("list", [{}])[0].get("coin", []):
            if c.get("coin") == "USDT":
                total += _safe_float(c.get("walletBalance")) or _safe_float(c.get("equity"))
    # Funding account
    fund = _bybit_signed_get("/v5/asset/transfer/query-asset-info", "coin=USDT")
    if fund and fund.get("retCode") == 0:
        for item in fund.get("result", {}).get("list", []):
            if item.get("coin") == "USDT":
                total += _safe_float(item.get("walletBalance"))
    return total


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
    """Fetch Gate.io USDT balance across spot + earn + margin."""
    total = 0.0
    for path in ("/api/v4/spot/accounts", "/api/v4/earn/uni/interests", "/api/v4/margin/accounts"):
        data = _gate_signed_get(path)
        if not data or not isinstance(data, list):
            continue
        for coin in data:
            cur = coin.get("currency", coin.get("coin", ""))
            if cur == "USDT":
                total += _safe_float(coin.get("available", coin.get("amount", 0)))
                total += _safe_float(coin.get("locked", 0))
    return total


def _fetch_gate_balances() -> list[dict]:
    """Fetch all Gate.io balances across spot + earn."""
    merged: dict[str, float] = {}
    for path in ("/api/v4/spot/accounts", "/api/v4/earn/uni/interests"):
        data = _gate_signed_get(path)
        if not data or not isinstance(data, list):
            continue
        for coin in data:
            sym = coin.get("currency", coin.get("coin", ""))
            available = _safe_float(coin.get("available", coin.get("amount", 0)))
            locked = _safe_float(coin.get("locked", 0))
            if sym and sym not in ("USDT", "USD", "USDC"):
                merged[sym] = merged.get(sym, 0) + available + locked
    result = []
    for sym, total in merged.items():
        if total <= 0:
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


def _kucoin_signed_post(path: str, body: dict) -> dict | None:
    """KuCoin v2 API signed POST request (for placing orders / transfers)."""
    if not KUCOIN_KEY or not KUCOIN_SECRET:
        return None
    import base64
    ts = str(int(time.time() * 1000))
    body_str = json.dumps(body)
    sign_str = f"{ts}POST{path}{body_str}"
    sig = base64.b64encode(
        hmac.new(KUCOIN_SECRET.encode(), sign_str.encode(), hashlib.sha256).digest()
    ).decode()
    passphrase = base64.b64encode(
        hmac.new(KUCOIN_SECRET.encode(), KUCOIN_PASS.encode(), hashlib.sha256).digest()
    ).decode()
    url = f"https://api.kucoin.com{path}"
    try:
        req = _urllib_req.Request(url, data=body_str.encode(), headers={
            "KC-API-KEY": KUCOIN_KEY,
            "KC-API-SIGN": sig,
            "KC-API-TIMESTAMP": ts,
            "KC-API-PASSPHRASE": passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json",
        }, method="POST")
        with _urllib_req.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"KuCoin POST {path}: {e}")
        # surface the HTTP error body so the caller can show a real reason
        try:
            return json.loads(e.read())  # type: ignore[attr-defined]
        except Exception:
            return {"code": "ERROR", "msg": str(e)}


def _kucoin_symbol_info(symbol: str) -> dict:
    """Return baseIncrement / baseMinSize / quoteMinSize for a SYMBOL-USDT pair."""
    pair = f"{symbol.upper()}-USDT"
    data = _http_get(f"https://api.kucoin.com/api/v2/symbols/{pair}")
    if data and data.get("code") == "200000":
        d = data.get("data", {})
        if d:
            return {"baseIncrement": _safe_float(d.get("baseIncrement")) or 0.0001,
                    "baseMinSize": _safe_float(d.get("baseMinSize")) or 0.0,
                    "quoteMinSize": _safe_float(d.get("quoteMinSize")) or 0.1}
    return {"baseIncrement": 0.0001, "baseMinSize": 0.0, "quoteMinSize": 0.1}


def _execute_kucoin_buy(symbol: str, usd: float) -> str:
    """Market-buy a coin on KuCoin using USDT (funds). Tops up trade USDT from main."""
    coin = symbol.upper()
    pair = f"{coin}-USDT"
    info = _kucoin_symbol_info(coin)
    if usd < info["quoteMinSize"] or usd < 1.0:
        return f"❌ مبلغ الشراء (${usd:.2f}) أقل من الحد الأدنى ({info['quoteMinSize']})"

    trade_usdt = _fetch_kucoin_coin_balance("USDT", "trade")
    main_usdt = _fetch_kucoin_coin_balance("USDT", "main")
    if trade_usdt + main_usdt < usd:
        return f"❌ رصيد USDT غير كافٍ على KuCoin (${trade_usdt+main_usdt:.2f} < ${usd:.2f})"

    # KuCoin buys from the trade account — top it up from main if short
    if trade_usdt < usd:
        need = usd - trade_usdt
        if main_usdt >= need:
            if not _kucoin_inner_transfer("USDT", need, "main", "trade"):
                return "❌ تعذّر نقل USDT من main إلى trade على KuCoin"
            time.sleep(1)

    body = {
        "clientOid": _secrets.token_hex(12),
        "side": "buy",
        "symbol": pair,
        "type": "market",
        "funds": f"{usd:.4f}",
    }
    res = _kucoin_signed_post("/api/v1/orders", body)
    if res and res.get("code") == "200000":
        price = _fetch_kucoin_price(coin) or 0
        log(f"KuCoin BUY: {coin} بـ ${usd:.2f} @ ~${price}")
        return (f"✅ تم شراء {coin} على KuCoin\n"
                f"المبلغ: ${usd:.2f}\nالسعر: ~${price:,.6f}")
    msg = res.get("msg", "unknown") if res else "no response"
    code = res.get("code", "?") if res else "?"
    log(f"KuCoin BUY FAILED: {coin} — {code}: {msg}")
    return f"❌ فشل الشراء على KuCoin: {code} — {msg}"


def _fetch_kucoin_coin_balance(coin: str, acct_type: str) -> float:
    """Available balance of a coin in a specific KuCoin account (trade/main)."""
    coin = coin.upper().replace("USDT", "")
    data = _kucoin_signed_get(f"/api/v1/accounts?type={acct_type}")
    if data and data.get("code") == "200000":
        for acc in data.get("data", []):
            if acc.get("currency") == coin:
                return _safe_float(acc.get("available"))
    return 0.0


def _kucoin_inner_transfer(coin: str, amount: float, frm: str, to: str) -> bool:
    """Move a coin between KuCoin accounts (e.g. main → trade so it's sellable)."""
    body = {
        "clientOid": _secrets.token_hex(12),
        "currency": coin.upper(),
        "from": frm,
        "to": to,
        "amount": _qty_str(amount),
    }
    res = _kucoin_signed_post("/api/v2/accounts/inner-transfer", body)
    ok = bool(res and res.get("code") == "200000")
    if not ok:
        log(f"KuCoin transfer {coin} {frm}->{to} فشل: {res}")
    return ok


def _execute_kucoin_sell(symbol: str, sell_pct: float, profit_only: bool = False,
                         out: dict | None = None) -> str:
    """Market-sell a coin on KuCoin. Moves it main→trade first if needed.
    If `out` is given, it's filled with {ok, price, qty, value} for callers
    (e.g. the auto-cycle) that need the realized amount."""
    coin = symbol.upper()
    pair = f"{coin}-USDT"
    price = _fetch_kucoin_price(coin)
    if not price:
        return f"❌ لم أستطع جلب سعر {pair} على KuCoin"

    trade_bal = _fetch_kucoin_coin_balance(coin, "trade")
    main_bal = _fetch_kucoin_coin_balance(coin, "main")
    total = trade_bal + main_bal
    if total <= 0:
        return f"❌ لا يوجد رصيد من {coin} على KuCoin"

    # profit-only: sell just the gain portion, keep original investment
    if profit_only:
        entry = 0.0
        for h in _get_kucoin_holdings_with_entry():
            if h["symbol"].upper() == coin:
                entry = h.get("entry", 0)
                break
        if not entry or entry <= 0:
            return f"❌ لا أعرف سعر دخول {coin} — استخدم: بيع {coin} 50%"
        if price <= entry:
            pnl_pct = ((price - entry) / entry) * 100
            return f"❌ {coin} في خسارة ({pnl_pct:+.1f}%) — لا ربح لجنيه"
        sell_pct = ((price - entry) / price) * 100

    sell_qty = total * (sell_pct / 100.0)

    info = _kucoin_symbol_info(coin)
    sell_qty = _round_qty(sell_qty, info["baseIncrement"])
    if sell_qty <= 0 or (info["baseMinSize"] and sell_qty < info["baseMinSize"]):
        return f"❌ الكمية ({_qty_str(sell_qty)}) أقل من الحد الأدنى ({info['baseMinSize']})"
    if sell_qty * price < 1.0:
        return f"❌ قيمة البيع أقل من $1 ({_qty_str(sell_qty)} ≈ ${sell_qty*price:.2f})"

    # KuCoin can only sell from the trade account — top it up from main if short
    if trade_bal < sell_qty:
        need = sell_qty - trade_bal
        if main_bal >= need:
            if not _kucoin_inner_transfer(coin, need, "main", "trade"):
                return f"❌ تعذّر نقل {coin} من main إلى trade على KuCoin"
            time.sleep(1)
        else:
            return f"❌ رصيد trade غير كافٍ ({_qty_str(trade_bal)}) ولا يمكن إكماله من main"

    body = {
        "clientOid": _secrets.token_hex(12),
        "side": "sell",
        "symbol": pair,
        "type": "market",
        "size": _qty_str(sell_qty),
    }
    res = _kucoin_signed_post("/api/v1/orders", body)
    if res and res.get("code") == "200000":
        value = sell_qty * price
        if out is not None:
            out.update({"ok": True, "price": price, "qty": sell_qty, "value": value})
        label = "بيع ربح" if profit_only else f"بيع {sell_pct:.0f}%"
        log(f"KuCoin SELL: {coin} {label} qty={sell_qty} @ ${price}")
        return (f"✅ تم {label} من {coin} على KuCoin\n"
                f"الكمية: {_qty_str(sell_qty)}\n"
                f"السعر: ${price:,.6f}\n"
                f"القيمة: ${value:,.2f}")
    if out is not None:
        out.update({"ok": False})
    msg = res.get("msg", "unknown") if res else "no response"
    code = res.get("code", "?") if res else "?"
    log(f"KuCoin SELL FAILED: {coin} — {code}: {msg}")
    return f"❌ فشل البيع على KuCoin: {code} — {msg}"


# ══════════════════════════════════════════════════════════════
# KUCOIN AUTO-CYCLE (profit-harvest + re-buy grid)
#   عند ارتفاع +10% فوق سعر المرجع → بيع الربح، وتسجيل سعر البيع.
#   عند هبوط -15% تحت سعر البيع → إعادة الشراء بنفس قيمة البيع.
#   تتكرر الدورة حتى بلوغ هدف الربح لكل عملة (إن وُجد).
# ══════════════════════════════════════════════════════════════
KUCOIN_CYCLE_STATE = BASE_DIR / "kucoin_cycle_state.json"
CYCLE_RISE_PCT = float(os.getenv("KUCOIN_CYCLE_RISE", "10"))
CYCLE_DROP_PCT = float(os.getenv("KUCOIN_CYCLE_DROP", "15"))
CYCLE_INTERVAL = int(os.getenv("KUCOIN_CYCLE_SEC", "180"))
CYCLE_MIN_ORDER = 1.0


def _load_cycle() -> dict:
    if KUCOIN_CYCLE_STATE.exists():
        try:
            return json.loads(KUCOIN_CYCLE_STATE.read_text())
        except Exception:
            pass
    return {"enabled": False, "default_target": 0.0, "coins": {}}


def _save_cycle(cyc: dict) -> None:
    tmp = KUCOIN_CYCLE_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cyc, ensure_ascii=False, indent=2))
    os.replace(tmp, KUCOIN_CYCLE_STATE)


def run_kucoin_cycle() -> None:
    """One tick of the KuCoin auto-cycle. Safe to call repeatedly."""
    if not KUCOIN_KEY:
        return
    cyc = _load_cycle()
    if not cyc.get("enabled"):
        return

    try:
        holdings = {h["symbol"].upper(): h for h in _get_kucoin_holdings_with_entry()}
    except Exception as e:
        log(f"CYCLE: فشل جلب أرصدة KuCoin: {e}")
        return

    coins = cyc.setdefault("coins", {})
    default_target = cyc.get("default_target", 0.0)

    # auto-enroll every KuCoin holding (scope = all)
    for sym, h in holdings.items():
        if sym not in coins:
            ref = h.get("entry") or h.get("price") or 0
            coins[sym] = {
                "ref_price": ref, "last_sell_price": 0.0,
                "pending_rebuy_usd": 0.0, "phase": "holding",
                "harvested": 0.0, "target": default_target,
                "cycles": 0, "done": False,
            }

    changed = False
    for sym, c in coins.items():
        if c.get("done"):
            continue
        price = _fetch_kucoin_price(sym)
        if not price or price <= 0:
            continue

        phase = c.get("phase", "holding")

        # ── HOLDING: wait for +RISE% over the reference, then harvest profit ──
        if phase == "holding":
            ref = c.get("ref_price") or 0
            if ref <= 0:
                c["ref_price"] = price
                changed = True
                continue
            if price >= ref * (1 + CYCLE_RISE_PCT / 100):
                # sell the gain portion relative to the cycle reference
                profit_pct = ((price - ref) / price) * 100
                out: dict = {}
                _execute_kucoin_sell(sym, profit_pct, out=out)
                if out.get("ok"):
                    sold_usd = out["value"]
                    profit_usd = (price - ref) * out["qty"]
                    c["last_sell_price"] = price
                    c["pending_rebuy_usd"] = sold_usd
                    c["phase"] = "waiting_rebuy"
                    c["harvested"] = c.get("harvested", 0.0) + profit_usd
                    c["cycles"] = c.get("cycles", 0) + 1
                    changed = True
                    notify(f"🔄 دورة KuCoin: بيع ربح <b>{sym}</b>\n"
                           f"ارتفع +{CYCLE_RISE_PCT:.0f}% → بِعت ${sold_usd:.2f} @ ${price:,.6f}\n"
                           f"ربح هذه الدورة: ${profit_usd:+.2f} | إجمالي: ${c['harvested']:+.2f}\n"
                           f"⏳ سأعيد الشراء عند -{CYCLE_DROP_PCT:.0f}%")
                    tgt = c.get("target", 0.0)
                    if tgt and c["harvested"] >= tgt:
                        c["done"] = True
                        notify(f"🎯 دورة KuCoin: <b>{sym}</b> بلغت هدف الربح "
                               f"${tgt:.2f} (محقق ${c['harvested']:.2f}) — توقفت.")

        # ── WAITING_REBUY: wait for -DROP% under the sell price, then re-buy ──
        elif phase == "waiting_rebuy":
            sp = c.get("last_sell_price") or 0
            if sp <= 0:
                c["phase"] = "holding"
                changed = True
                continue
            if price <= sp * (1 - CYCLE_DROP_PCT / 100):
                usd = c.get("pending_rebuy_usd", 0.0)
                if usd < CYCLE_MIN_ORDER:
                    c["phase"] = "holding"
                    c["ref_price"] = price
                    changed = True
                    continue
                res = _execute_kucoin_buy(sym, usd)
                if res.startswith("✅"):
                    c["ref_price"] = price
                    c["pending_rebuy_usd"] = 0.0
                    c["phase"] = "holding"
                    changed = True
                    notify(f"🔄 دورة KuCoin: إعادة شراء <b>{sym}</b>\n"
                           f"هبط -{CYCLE_DROP_PCT:.0f}% → اشتريت ${usd:.2f} @ ${price:,.6f}\n"
                           f"🔁 الدورة #{c.get('cycles',0)+1} بدأت")

    if changed:
        _save_cycle(cyc)


def _cycle_loop() -> None:
    """Background thread: run the KuCoin auto-cycle every CYCLE_INTERVAL seconds."""
    log(f"CYCLE: حلقة دورة KuCoin بدأت (كل {CYCLE_INTERVAL}s)")
    while True:
        try:
            run_kucoin_cycle()
        except Exception as e:
            log(f"CYCLE error: {e}")
        time.sleep(CYCLE_INTERVAL)


def _fetch_kucoin_balances() -> list[dict]:
    """Fetch KuCoin balances across trade + main accounts with value > $1."""
    merged: dict[str, float] = {}
    for acct_type in ("trade", "main"):
        data = _kucoin_signed_get(f"/api/v1/accounts?type={acct_type}")
        if not data or data.get("code") != "200000":
            continue
        for acc in data.get("data", []):
            sym = acc.get("currency", "")
            bal = _safe_float(acc.get("balance"))
            if bal > 0 and sym not in ("USDT", "USD", "USDC"):
                merged[sym] = merged.get(sym, 0) + bal
    result = []
    for sym, total in merged.items():
        if total <= 0:
            continue
        price = _fetch_kucoin_price(sym)
        if not price:
            continue
        value = total * price
        if value < 1.0:
            continue
        result.append({"symbol": sym, "amount": total, "price": price, "value": value})
    return result


def _fetch_kucoin_usdt() -> float:
    """Fetch KuCoin USDT balance across trade + main accounts."""
    total = 0.0
    for acct_type in ("trade", "main"):
        data = _kucoin_signed_get(f"/api/v1/accounts?type={acct_type}")
        if data and data.get("code") == "200000":
            for acc in data.get("data", []):
                if acc.get("currency") == "USDT":
                    total += _safe_float(acc.get("balance"))
    return total


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


def _get_bybit_holdings_with_entry() -> list[dict]:
    """Bybit holdings with entry prices from bot states + portfolio_state.json."""
    if not BYBIT_KEY:
        return []

    # Collect entry prices from bot state files first (most accurate)
    entry_prices: dict[str, tuple[float, str]] = {}
    positions = get_all_positions()
    for p in positions:
        sym = p["symbol"]
        entry = p.get("entry", 0)
        if entry and entry > 0:
            entry_prices[sym] = (entry, p.get("bot", ""))

    # Fallback: portfolio_state.json @Bybit entries
    if PORTFOLIO_STATE.exists():
        try:
            pstate = json.loads(PORTFOLIO_STATE.read_text())
            for key, entry in pstate.get("entry_prices", {}).items():
                if "@Bybit" in key:
                    sym = key.split("@")[0]
                    if sym not in entry_prices:
                        entry_prices[sym] = (entry, "")
        except Exception:
            pass

    # Scan actual Bybit wallet
    coins: dict[str, float] = {}
    data = _bybit_signed_get("/v5/account/wallet-balance", "accountType=UNIFIED")
    if data and data.get("retCode") == 0:
        for c in data.get("result", {}).get("list", [{}])[0].get("coin", []):
            sym = c.get("coin", "")
            if sym in ("USDT", "USD", "USDC") or not sym:
                continue
            bal = _safe_float(c.get("walletBalance"))
            if bal > 0:
                coins[sym] = coins.get(sym, 0) + bal
    fund = _bybit_signed_get("/v5/asset/transfer/query-asset-info", "coin=")
    if fund and fund.get("retCode") == 0:
        for item in fund.get("result", {}).get("list", []):
            sym = item.get("coin", "")
            if sym in ("USDT", "USD", "USDC") or not sym:
                continue
            bal = _safe_float(item.get("availableToWithdraw"))
            if bal > 0:
                coins[sym] = coins.get(sym, 0) + bal

    holdings = []
    for sym, amount in coins.items():
        price = _fetch_price(f"{sym}USDT")
        if not price:
            continue
        value = amount * price
        if value < 1.0:
            continue
        entry, bot = entry_prices.get(sym, (0, ""))
        holdings.append({
            "symbol": sym,
            "amount": amount,
            "price": price,
            "value": value,
            "entry": entry,
            "bot": bot,
        })
    return holdings


def _load_capital() -> dict:
    if CAPITAL_CONFIG.exists():
        try:
            return json.loads(CAPITAL_CONFIG.read_text())
        except Exception:
            pass
    return {}


def _save_capital(cfg: dict):
    tmp = CAPITAL_CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    os.replace(tmp, CAPITAL_CONFIG)


def _coin_to_usdt(coin: str, amount: float) -> float:
    """Convert a coin amount to USDT value. Returns 0 if price unavailable."""
    if coin in ("USDT", "USDC", "USD", "BUSD", "DAI"):
        return amount
    price = _fetch_price(f"{coin}USDT") or _fetch_gate_price(coin) or _fetch_kucoin_price(coin)
    return amount * price if price else 0.0


def _bybit_paginated_get(path: str, base_params: str, label: str) -> list[dict]:
    """Fetch all pages from a Bybit endpoint."""
    all_rows = []
    cursor = ""
    for _ in range(20):
        params = base_params
        if cursor:
            params += f"&cursor={cursor}"
        data = _bybit_signed_get(path, params)
        if not data:
            log(f"Bybit {label}: no response")
            break
        if data.get("retCode") != 0:
            log(f"Bybit {label}: {data.get('retCode')} — {data.get('retMsg', '')}")
            break
        rows = data.get("result", {}).get("rows", [])
        all_rows.extend(rows)
        cursor = data.get("result", {}).get("nextPageCursor", "")
        if not cursor or not rows:
            break
    return all_rows


def _fetch_bybit_deposits_withdrawals() -> tuple[float, float]:
    """Fetch total deposits and withdrawals from Bybit (last 6 months).
    Includes on-chain deposits AND internal transfers (P2P, sub-account)."""
    if not BYBIT_KEY:
        return 0.0, 0.0
    start_ms = str(int((time.time() - 180 * 86400) * 1000))
    end_ms = str(int(time.time() * 1000))
    base = f"startTime={start_ms}&endTime={end_ms}&limit=50"

    total_dep = 0.0

    # On-chain deposits
    rows = _bybit_paginated_get("/v5/asset/deposit/query-record", base, "on-chain deposits")
    for r in rows:
        if r.get("status") in (3, "3", 4, "4", 1, "1", 10000, "10000"):
            total_dep += _coin_to_usdt(r.get("coin", ""), _safe_float(r.get("amount")))
    log(f"Bybit on-chain deposits: ${total_dep:,.2f} ({len(rows)} records)")

    # Internal deposits (P2P, sub-account transfers, etc.)
    internal_dep = 0.0
    rows = _bybit_paginated_get("/v5/asset/deposit/query-internal-record", base, "internal deposits")
    for r in rows:
        if r.get("status") in (3, "3", 1, "1"):
            internal_dep += _coin_to_usdt(r.get("coin", ""), _safe_float(r.get("amount")))
    total_dep += internal_dep
    log(f"Bybit internal deposits: ${internal_dep:,.2f} ({len(rows)} records)")

    total_wd = 0.0

    # On-chain withdrawals
    rows = _bybit_paginated_get("/v5/asset/withdraw/query-record",
                                base + "&withdrawType=2", "on-chain withdrawals")
    for r in rows:
        status = str(r.get("status", "")).lower()
        if status in ("success", "blockchainconfirmed"):
            total_wd += _coin_to_usdt(r.get("coin", ""), _safe_float(r.get("amount")))
    log(f"Bybit on-chain withdrawals: ${total_wd:,.2f} ({len(rows)} records)")

    # Internal withdrawals
    internal_wd = 0.0
    rows = _bybit_paginated_get("/v5/asset/withdraw/query-internal-record", base, "internal withdrawals")
    for r in rows:
        if r.get("status") in (3, "3", 1, "1"):
            internal_wd += _coin_to_usdt(r.get("coin", ""), _safe_float(r.get("amount")))
    total_wd += internal_wd
    log(f"Bybit internal withdrawals: ${internal_wd:,.2f} ({len(rows)} records)")

    log(f"Bybit TOTAL: deposits=${total_dep:,.2f}, withdrawals=${total_wd:,.2f}")
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
    """Fetch deposits/withdrawals from all exchanges. Returns summary dict.
    If manual capital is set, uses that as total_deposited instead."""
    result = {"exchanges": {}, "total_deposited": 0.0, "total_withdrawn": 0.0, "manual": False}

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

    cap = _load_capital()
    if cap.get("total_deposited"):
        result["total_deposited"] = cap["total_deposited"]
        result["manual"] = True
    if cap.get("total_withdrawn"):
        result["total_withdrawn"] = cap["total_withdrawn"]

    return result


def _locate_coin(symbol: str) -> list[str]:
    """Return the list of non-Bybit exchanges that hold this coin (for clearer errors)."""
    sym = symbol.upper()
    found = []
    try:
        if GATE_KEY and any(b["symbol"].upper() == sym for b in _fetch_gate_balances()):
            found.append("Gate")
    except Exception:
        pass
    try:
        if KUCOIN_KEY and any(b["symbol"].upper() == sym for b in _fetch_kucoin_balances()):
            found.append("KuCoin")
    except Exception:
        pass
    return found


def _execute_sell(symbol: str, sell_pct: float) -> str:
    """Execute a sell order. symbol is base coin (e.g. 'ENJ'). sell_pct is 1-100.
    Routes to Bybit if held there, otherwise KuCoin. Gate stays view-only."""
    if not BYBIT_KEY or not BYBIT_SECRET:
        return "❌ مفاتيح Bybit غير متوفرة"

    pair = f"{symbol.upper()}USDT"
    free = _fetch_coin_balance(symbol)
    if free <= 0:
        # not on Bybit — try KuCoin (Gate is view-only)
        if KUCOIN_KEY and any(b["symbol"].upper() == symbol.upper()
                              for b in _fetch_kucoin_balances()):
            return _execute_kucoin_sell(symbol, sell_pct)
        other = _locate_coin(symbol)
        if other:
            return (f"❌ {symbol} غير موجودة على Bybit — هي على {', '.join(other)}.\n"
                    f"⚠️ Gate للعرض فقط (بِع يدوياً على المنصّة).")
        return f"❌ لا يوجد رصيد من {symbol} في المحفظة"

    price = _fetch_price(pair)
    if not price:
        return f"❌ لم أستطع جلب سعر {pair}"

    sell_qty = free * (sell_pct / 100.0)

    step = _get_lot_step(pair)
    sell_qty = _round_qty(sell_qty, step)

    if sell_qty <= 0:
        return f"❌ الكمية صفر بعد التقريب (step={step})"

    # Re-check the $1 minimum AFTER rounding — rounding down can drop it below $1.
    value_usd = sell_qty * price
    if value_usd < 1.0:
        return f"❌ قيمة البيع أقل من $1 ({symbol}: {sell_qty:.6f} ≈ ${value_usd:.2f})"

    result = _bybit_signed_post({
        "category": "spot",
        "symbol": pair,
        "side": "Sell",
        "orderType": "Market",
        "qty": _qty_str(sell_qty),
        "marketUnit": "baseCoin",
    })

    if result and result.get("_ambiguous"):
        return (f"⚠️ انقطع الاتصال أثناء بيع {symbol} — قد يكون الأمر نُفِّذ!\n"
                f"❗️لا تُعد الإرسال. تحقق من الرصيد في Bybit أولاً (أمر «رصيد»).\n"
                f"orderLinkId: {result.get('orderLinkId','')}")

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


def _scan_profitable_coins() -> str:
    """Scan ALL exchange holdings, rank by profit, suggest sells."""
    all_holdings: list[dict] = []
    if BYBIT_KEY:
        for h in _get_bybit_holdings_with_entry():
            h["exchange"] = "Bybit"
            h["can_sell"] = True
            all_holdings.append(h)
    if GATE_KEY:
        for h in _get_gate_holdings_with_entry():
            h["exchange"] = "Gate"
            h["can_sell"] = False
            all_holdings.append(h)
    if KUCOIN_KEY:
        for h in _get_kucoin_holdings_with_entry():
            h["exchange"] = "KuCoin"
            h["can_sell"] = True
            all_holdings.append(h)

    if not all_holdings:
        return "📭 لا توجد مراكز مفتوحة"

    # compute PnL for each holding
    for h in all_holdings:
        entry = h.get("entry", 0)
        price = h.get("price", 0)
        if not entry or not price or entry <= 0:
            h.update({"pnl_pct": 0, "pnl_usd": 0, "profit_sell_pct": 0, "skip": True})
            continue
        pnl_pct = ((price - entry) / entry) * 100
        pnl_usd = (price - entry) * h["amount"]
        profit_sell_pct = max(0, ((price - entry) / price) * 100)
        h.update({"pnl_pct": pnl_pct, "pnl_usd": pnl_usd, "profit_sell_pct": profit_sell_pct, "skip": False})

    # aggregate net PnL per symbol across exchanges
    sym_net: dict[str, float] = {}
    for h in all_holdings:
        if h.get("skip"):
            continue
        sym_net[h["symbol"]] = sym_net.get(h["symbol"], 0) + h["pnl_usd"]

    # net-losers = symbols that are overall losing across all exchanges → buy more
    net_losers = {s for s, pnl in sym_net.items() if pnl < 0}

    # split: pure winners (not net-losers) vs losers
    profitable = [h for h in all_holdings if not h.get("skip") and h["pnl_pct"] > 0 and h["symbol"] not in net_losers]
    buy_more = [h for h in all_holdings if not h.get("skip") and h["symbol"] in net_losers]
    profitable.sort(key=lambda x: x["pnl_pct"], reverse=True)
    buy_more.sort(key=lambda x: sym_net.get(x["symbol"], 0))

    lines = ["<b>💰 فرص — مرتبة بالربح</b>\n"]

    # ── توصية رئيسية ──
    if profitable and buy_more:
        top = profitable[0]
        # pick the worst net-loser symbol
        worst_sym = min(net_losers, key=lambda s: sym_net[s])
        total_profit = sum(p["pnl_usd"] for p in profitable)
        how = "بيع بأمر البوت" if top["can_sell"] else f"بيع يدوي على {top['exchange']}"
        lines.append("<b>💡 التوصية:</b>")
        lines.append(
            f"  بيع ربح <b>{top['symbol']}</b> [{top['exchange']}] ({top['pnl_pct']:+.1f}% = ${top['pnl_usd']:+,.2f}) — {how}"
            f"\n  ← شراء/تعزيز <b>{worst_sym}</b> (صافي: ${sym_net[worst_sym]:+,.2f})"
            f"\n  إجمالي أرباح قابلة للجني: <b>${total_profit:,.2f}</b>\n"
        )

    if profitable:
        lines.append("<b>🟢 عملات مرتفعة (بيع):</b>")
        for p in profitable:
            sell_pct = round(p["profit_sell_pct"])
            if sell_pct < 1:
                sell_pct = 1
            entry_line = (
                f"\n  <b>{p['symbol']}</b> [{p['exchange']}] — <b>{p['pnl_pct']:+.1f}%</b>"
                f" (${p['pnl_usd']:+,.2f})"
            )
            if p["can_sell"]:
                entry_line += (
                    f"\n  ✂️ <code>بيع ربح {p['symbol']}</code> ({sell_pct}%)"
                    f" | 🔄 <code>بيع {p['symbol']} 50%</code>"
                )
            lines.append(entry_line)
    else:
        lines.append("⚪ لا توجد عملات صافي ربحها موجب")

    if buy_more:
        # deduplicate by symbol, show net PnL
        shown = set()
        lines.append(f"\n<b>🔵 عملات للتعزيز/الشراء ({len(net_losers)}):</b>")
        for sym in sorted(net_losers, key=lambda s: sym_net[s]):
            if sym in shown:
                continue
            shown.add(sym)
            net = sym_net[sym]
            entries = [h for h in buy_more if h["symbol"] == sym]
            exchanges = ", ".join(f"{h['exchange']} {h['pnl_pct']:+.1f}%" for h in entries)
            lines.append(f"  <b>{sym}</b>: صافي ${net:+,.2f} ({exchanges})")

    return "\n".join(lines)


def _execute_profit_sell(symbol: str) -> str:
    """Sell only the profit portion of a coin, keeping the original investment.
    Routes to Bybit if held there, otherwise KuCoin. Gate stays view-only."""
    if not BYBIT_KEY or not BYBIT_SECRET:
        return "❌ مفاتيح Bybit غير متوفرة"

    # not on Bybit — try KuCoin (Gate is view-only)
    if _fetch_coin_balance(symbol) <= 0:
        if KUCOIN_KEY and any(b["symbol"].upper() == symbol.upper()
                              for b in _fetch_kucoin_balances()):
            return _execute_kucoin_sell(symbol, 100.0, profit_only=True)

    # Find entry price from bot state files
    entry = 0.0
    bot_name = ""
    for p in get_all_positions():
        if p["symbol"] == symbol.upper():
            entry = p["entry"]
            bot_name = p["bot"]
            break

    if not entry:
        other = _locate_coin(symbol)
        if other:
            return (f"❌ {symbol} على {', '.join(other)} وليست على Bybit.\n"
                    f"⚠️ Gate للعرض فقط (بِع يدوياً على المنصّة).")
        return f"❌ لم أجد سعر دخول لـ {symbol}"

    pair = f"{symbol.upper()}USDT"
    price = _fetch_price(pair)
    if not price:
        other = _locate_coin(symbol)
        if other:
            return (f"❌ {symbol} على {', '.join(other)} وليست على Bybit.\n"
                    f"⚠️ البيع عبر البوت يدعم Bybit فقط.")
        return f"❌ لم أستطع جلب سعر {pair}"

    if price <= entry:
        pnl_pct = ((price - entry) / entry) * 100
        return f"❌ {symbol} حالياً في خسارة ({pnl_pct:+.1f}%)\nدخول: ${entry:,.4f} → حالي: ${price:,.4f}"

    # Calculate profit-only sell percentage
    # If entry=$2, current=$2.50, profit portion = ($2.50-$2.00)/$2.50 = 20%
    profit_pct = ((price - entry) / price) * 100

    free = _fetch_coin_balance(symbol)
    if free <= 0:
        return f"❌ لا يوجد رصيد من {symbol}"

    profit_qty = free * (profit_pct / 100.0)

    step = _get_lot_step(pair)
    profit_qty = _round_qty(profit_qty, step)
    if profit_qty <= 0:
        return f"❌ كمية الربح صفر بعد التقريب (step={step})"

    # Re-check the $1 minimum AFTER rounding.
    profit_value = profit_qty * price
    if profit_value < 1.0:
        return (f"❌ قيمة الربح أقل من $1\n"
                f"{symbol}: ربح {profit_pct:.1f}% = {_qty_str(profit_qty)} ≈ ${profit_value:.2f}")

    result = _bybit_signed_post({
        "category": "spot",
        "symbol": pair,
        "side": "Sell",
        "orderType": "Market",
        "qty": _qty_str(profit_qty),
        "marketUnit": "baseCoin",
    })

    if result and result.get("_ambiguous"):
        return (f"⚠️ انقطع الاتصال أثناء بيع ربح {symbol} — قد يكون الأمر نُفِّذ!\n"
                f"❗️لا تُعد الإرسال. تحقق من الرصيد في Bybit أولاً (أمر «رصيد»).\n"
                f"orderLinkId: {result.get('orderLinkId','')}")

    if result and result.get("retCode") == 0:
        remaining = free - profit_qty
        msg = (f"✅ تم بيع ربح {symbol} فقط\n"
               f"الكمية المباعة: {_qty_str(profit_qty)} ({profit_pct:.1f}%)\n"
               f"القيمة: ${profit_value:,.2f}\n"
               f"المتبقي: {_qty_str(remaining)} {symbol} (رأس المال الأصلي)\n"
               f"دخول: ${entry:,.4f} | بيع: ${price:,.4f}")
        log(f"PROFIT SELL: {symbol} — qty={profit_qty} ({profit_pct:.1f}%) @ ${price}")
        return msg

    err_msg = result.get("retMsg", "unknown") if result else "no response"
    return f"❌ فشل البيع: {err_msg}"


def _handle_command(text: str) -> str | None:
    """Parse and execute a Telegram command. Returns reply text or None."""
    text = text.strip()
    if not text:
        return None

    # ── بيع ربح / sell profit ──
    profit_sell = re.match(
        r"(?:بيع ربح|sell profit)\s+([A-Za-z]+)",
        text, re.IGNORECASE
    )
    if profit_sell:
        symbol = profit_sell.group(1).upper()
        return _execute_profit_sell(symbol)

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

    # ── فرص / opportunities ──
    if text in ("فرص", "opportunities", "/opportunities", "ارباح اليوم"):
        return _scan_profitable_coins()

    # ── دورة KuCoin التلقائية ──
    if text in ("دورة تشغيل", "دوره تشغيل", "cycle on"):
        cyc = _load_cycle()
        cyc["enabled"] = True
        _save_cycle(cyc)
        return (f"✅ تفعّلت الدورة التلقائية على KuCoin\n"
                f"بيع الربح عند +{CYCLE_RISE_PCT:.0f}% | إعادة الشراء عند -{CYCLE_DROP_PCT:.0f}%\n"
                f"تشمل كل عملات KuCoin تلقائياً. فحص كل {CYCLE_INTERVAL//60} دقيقة.\n"
                f"💡 لضبط هدف ربح: <code>دورة هدف الرمز 50</code>")
    if text in ("دورة ايقاف", "دورة إيقاف", "دوره ايقاف", "cycle off"):
        cyc = _load_cycle()
        cyc["enabled"] = False
        _save_cycle(cyc)
        return "🛑 أُوقفت الدورة التلقائية (لن تُفتح صفقات جديدة)."
    cyc_target = re.match(r"(?:دورة|دوره)\s+هدف\s+([A-Za-z]+)\s+([\d.]+)", text, re.IGNORECASE)
    if cyc_target:
        sym = cyc_target.group(1).upper()
        tgt = float(cyc_target.group(2))
        cyc = _load_cycle()
        c = cyc.setdefault("coins", {}).setdefault(sym, {
            "ref_price": 0.0, "last_sell_price": 0.0, "pending_rebuy_usd": 0.0,
            "phase": "holding", "harvested": 0.0, "target": 0.0, "cycles": 0, "done": False})
        c["target"] = tgt
        c["done"] = False
        _save_cycle(cyc)
        return f"🎯 هدف ربح {sym} = ${tgt:.2f}. تتوقف الدورة عند بلوغه."
    if text in ("دورة", "دوره", "cycle", "/cycle"):
        cyc = _load_cycle()
        status = "🟢 مفعّلة" if cyc.get("enabled") else "🔴 متوقفة"
        lines = [f"<b>🔄 الدورة التلقائية (KuCoin)</b>\n",
                 f"الحالة: {status}",
                 f"بيع: +{CYCLE_RISE_PCT:.0f}% | شراء: -{CYCLE_DROP_PCT:.0f}% | فحص كل {CYCLE_INTERVAL//60}د\n"]
        coins = cyc.get("coins", {})
        if not coins:
            lines.append("لا عملات مسجّلة بعد (تُضاف تلقائياً عند التفعيل).")
        else:
            for sym, c in sorted(coins.items()):
                ph = "بانتظار شراء" if c.get("phase") == "waiting_rebuy" else "محتفظ"
                done = " ✅تم الهدف" if c.get("done") else ""
                tgt = f" | هدف ${c['target']:.0f}" if c.get("target") else ""
                lines.append(f"  {sym}: {ph} | دورات {c.get('cycles',0)} | "
                             f"ربح ${c.get('harvested',0):+.2f}{tgt}{done}")
        lines.append("\n<code>دورة تشغيل</code> / <code>دورة ايقاف</code> / <code>دورة هدف الرمز 50</code>")
        return "\n".join(lines)

    # ── تقرير / report ──
    if text in ("تقرير", "report", "/report"):
        lines = ["<b>📊 تقرير أداء البوتات الإجمالي</b>\n"]

        # smart_channel_bot
        if SMART_STATE.exists():
            try:
                ss = json.loads(SMART_STATE.read_text())
                history = ss.get("trade_history", [])
                positions = ss.get("open_positions", {})
                total_closed = len(history)
                total_pnl = sum(t.get("pnl", 0) for t in history)
                wins = sum(1 for t in history if t.get("pnl", 0) >= 0)
                losses = total_closed - wins
                wr = (wins / max(total_closed, 1)) * 100
                dp = ss.get("daily_pnl", 0)
                open_count = len(positions)
                icon = "🟢" if total_pnl >= 0 else "🔴"
                lines.append(
                    f"{icon} <b>━━ Smart Channel Bot ━━</b>\n"
                    f"  صفقات مغلقة: {total_closed} | مفتوحة: {open_count}\n"
                    f"  ربح: {wins} | خسارة: {losses} | نسبة الفوز: {wr:.0f}%\n"
                    f"  الربح الإجمالي (مغلقة): <b>${total_pnl:+,.2f}</b>\n"
                    f"  ربح اليوم: ${dp:+,.2f}"
                )
                if history:
                    best = max(history, key=lambda t: t.get("pnl", 0))
                    worst = min(history, key=lambda t: t.get("pnl", 0))
                    lines.append(
                        f"  أفضل صفقة: {best.get('pair','')} ${best.get('pnl',0):+,.2f}\n"
                        f"  أسوأ صفقة: {worst.get('pair','')} ${worst.get('pnl',0):+,.2f}"
                    )
            except Exception:
                lines.append("⚪ Smart Channel Bot — بيانات غير متوفرة")

        # monthly_channel_bot
        if MONTHLY_STATE.exists():
            try:
                ms = json.loads(MONTHLY_STATE.read_text())
                history = ms.get("trade_history", [])
                positions = ms.get("open_positions", {})
                total_closed = len(history)
                total_pnl = sum(t.get("pnl", 0) for t in history)
                wins = sum(1 for t in history if t.get("pnl", 0) >= 0)
                losses = total_closed - wins
                wr = (wins / max(total_closed, 1)) * 100
                open_count = len(positions)
                icon = "🟢" if total_pnl >= 0 else "🔴"
                lines.append(
                    f"\n{icon} <b>━━ Monthly Channel Bot ━━</b>\n"
                    f"  صفقات مغلقة: {total_closed} | مفتوحة: {open_count}\n"
                    f"  ربح: {wins} | خسارة: {losses} | نسبة الفوز: {wr:.0f}%\n"
                    f"  الربح الإجمالي (مغلقة): <b>${total_pnl:+,.2f}</b>"
                )
                if history:
                    best = max(history, key=lambda t: t.get("pnl", 0))
                    worst = min(history, key=lambda t: t.get("pnl", 0))
                    lines.append(
                        f"  أفضل صفقة: {best.get('pair','')} ${best.get('pnl',0):+,.2f}\n"
                        f"  أسوأ صفقة: {worst.get('pair','')} ${worst.get('pnl',0):+,.2f}"
                    )
            except Exception:
                lines.append("⚪ Monthly Channel Bot — بيانات غير متوفرة")

        return "\n".join(lines)

    # ── رأس مال / capital ──
    cap_match = re.match(
        r"(?:رأس مال|راس مال|رأسمال|capital)\s+([\d.]+)(?:\s+([\d.]+))?",
        text, re.IGNORECASE
    )
    if cap_match:
        try:
            dep = float(cap_match.group(1))
            wd = float(cap_match.group(2)) if cap_match.group(2) else 0
        except ValueError:
            return "❌ مبلغ غير صالح (مثال: رأس مال 1000 200)"
        if dep <= 0:
            return "❌ المبلغ يجب أن يكون أكبر من صفر"
        cfg = _load_capital()
        cfg["total_deposited"] = dep
        if wd > 0:
            cfg["total_withdrawn"] = wd
        cfg["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _save_capital(cfg)
        msg = f"✅ تم تسجيل رأس المال: ${dep:,.2f}"
        if wd > 0:
            msg += f"\nسحوبات: ${wd:,.2f}"
        msg += "\nسيُستخدم في حساب الربح الإجمالي بدلاً من بيانات API"
        return msg

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
            shown_syms = set()
            # All coins from UNIFIED account
            data = _bybit_signed_get("/v5/account/wallet-balance", "accountType=UNIFIED")
            if data and data.get("retCode") == 0:
                for c in data.get("result", {}).get("list", [{}])[0].get("coin", []):
                    sym = c.get("coin", "")
                    if sym in ("USDT", "USD", "USDC") or not sym:
                        continue
                    bal = _safe_float(c.get("walletBalance"))
                    if bal <= 0:
                        continue
                    price = _fetch_price(f"{sym}USDT")
                    val = bal * price if price else 0
                    if val < 1.0:
                        continue
                    shown_syms.add(sym)
                    bots = held.get(sym, [])
                    bot_label = f"  ({', '.join(bots)})" if bots else ""
                    bybit_total += val
                    lines.append(f"{sym}: {_qty_str(bal)} ≈ ${val:,.2f}{bot_label}")
            # Funding account coins not already shown
            fund = _bybit_signed_get("/v5/asset/transfer/query-asset-info", "coin=")
            if fund and fund.get("retCode") == 0:
                for item in fund.get("result", {}).get("list", []):
                    sym = item.get("coin", "")
                    if sym in ("USDT", "USD", "USDC") or sym in shown_syms or not sym:
                        continue
                    bal = _safe_float(item.get("availableToWithdraw"))
                    if bal <= 0:
                        continue
                    price = _fetch_price(f"{sym}USDT")
                    val = bal * price if price else 0
                    if val < 1.0:
                        continue
                    bybit_total += val
                    lines.append(f"{sym}: {_qty_str(bal)} ≈ ${val:,.2f}  (funding)")
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
            kc_usdt = _fetch_kucoin_usdt()
            kc_total = kc_usdt + sum(b["value"] for b in kc_bals)
            lines.append(f"\n<b>━━ KuCoin ━━</b>")
            if kc_usdt >= 1:
                lines.append(f"💵 USDT: ${kc_usdt:,.2f}")
            for b in sorted(kc_bals, key=lambda x: x["value"], reverse=True):
                lines.append(f"{b['symbol']}: {_qty_str(b['amount'])} ≈ ${b['value']:,.2f}")
            lines.append(f"<b>KuCoin: ${kc_total:,.2f}</b>")
            grand_total += kc_total

        lines.append(f"\n<b>القيمة الحالية: ${grand_total:,.2f}</b>")

        # إيداعات وسحوبات (per-exchange from API)
        dw = _fetch_all_deposits_withdrawals()
        total_dep = sum(v.get("deposited", 0) for v in dw["exchanges"].values())
        total_wd = sum(v.get("withdrawn", 0) for v in dw["exchanges"].values())
        if total_dep > 0 or total_wd > 0:
            net = total_dep - total_wd
            pnl = grand_total - net
            pnl_pct = (pnl / net * 100) if net > 0 else 0
            icon = "🟢" if pnl >= 0 else "🔴"
            lines.append(f"\n<b>━━ ملخص رأس المال ━━</b>")
            for ex, info in dw["exchanges"].items():
                if info.get("deposited", 0) > 0 or info.get("withdrawn", 0) > 0:
                    lines.append(f"  {ex}: إيداع ${info['deposited']:,.2f} | سحب ${info['withdrawn']:,.2f}")
            lines.append(
                f"\nإجمالي الإيداع: ${total_dep:,.2f}\n"
                f"إجمالي السحب: ${total_wd:,.2f}\n"
                f"صافي الاستثمار: ${net:,.2f}\n"
                f"{icon} <b>الربح/الخسارة: {pnl_pct:+.2f}% (${pnl:+,.2f})</b>"
            )

        return "\n".join(lines)

    # ── عملات / coins / holdings ──
    if text in ("عملات", "coins", "holdings", "/coins"):
        # Real wallet holdings per exchange (avoids phantom coins from stale
        # state files — only shows coins actually present in the wallet).
        held = get_all_held_coins()  # {SYM: [bot_names]} for bot attribution
        real: dict[str, list[str]] = {}  # SYM -> [exchange labels]
        if BYBIT_KEY:
            for h in _get_bybit_holdings_with_entry():
                real.setdefault(h["symbol"].upper(), []).append("Bybit")
        if GATE_KEY:
            for h in _fetch_gate_balances():
                real.setdefault(h["symbol"].upper(), []).append("Gate")
        if KUCOIN_KEY:
            for h in _fetch_kucoin_balances():
                real.setdefault(h["symbol"].upper(), []).append("KuCoin")

        if not real:
            return "📭 لا توجد عملات محتفظ بها حالياً"
        lines = ["<b>📊 العملات المحتفظ بها (الرصيد الفعلي)</b>\n"]
        for sym in sorted(real):
            exchanges = ", ".join(real[sym])
            bots = held.get(sym, [])
            bot_label = f" — بوت: {', '.join(bots)}" if bots else ""
            lines.append(f"  {sym}: {exchanges}{bot_label}")

        # Flag any stale state-file positions no longer in the wallet
        stale = [s for s in held if s not in real]
        if stale:
            lines.append(f"\n⚠️ في ملف البوت لكن غير موجودة بالمحفظة: {', '.join(stale)}")
        return "\n".join(lines)

    # ── أرباح / pnl ──
    if text in ("أرباح", "ارباح", "pnl", "/pnl", "ربح"):
        lines = ["<b>📈 أرباح/خسائر المراكز المفتوحة</b>\n"]
        total_cost = 0.0
        total_value = 0.0

        # ── Bybit ──
        if BYBIT_KEY:
            # Always render the section so the platform is visible even with no
            # open coin positions (e.g. bots holding only USDT cash).
            lines.append("<b>━━ Bybit ━━</b>")
            bybit_usdt = _fetch_usdt_balance()
            if bybit_usdt >= 1:
                lines.append(f"  💵 USDT متاح: ${bybit_usdt:,.2f}")
            bybit_holdings = _get_bybit_holdings_with_entry()
            if not bybit_holdings:
                lines.append("  📭 لا توجد مراكز عملات مفتوحة")
            else:
                bybit_cost = 0.0
                bybit_value = 0.0
                for h in sorted(bybit_holdings, key=lambda x: x["symbol"]):
                    sym = h["symbol"]
                    entry = h["entry"]
                    price = h["price"]
                    amount = h["amount"]
                    value = h["value"]
                    bot = h.get("bot", "")
                    bot_label = f" ({bot})" if bot else ""
                    if entry and entry > 0:
                        pnl_pct = ((price - entry) / entry) * 100
                        pnl_usd = (price - entry) * amount
                        icon = "🟢" if pnl_pct >= 0 else "🔴"
                        bybit_cost += entry * amount
                        bybit_value += value
                        lines.append(
                            f"  {icon} <b>{sym}</b>{bot_label}\n"
                            f"      دخول: ${entry:,.6f} → حالي: ${price:,.6f}\n"
                            f"      الربح: {pnl_pct:+.2f}% (${pnl_usd:+,.2f})"
                        )
                    else:
                        lines.append(
                            f"  ⚪ <b>{sym}</b>{bot_label}: ${price:,.6f} × {_qty_str(amount)} = ${value:,.2f}\n"
                            f"      سعر الدخول غير متوفر"
                        )
                if bybit_cost > 0:
                    b_pnl_pct = ((bybit_value - bybit_cost) / bybit_cost) * 100
                    b_pnl_usd = bybit_value - bybit_cost
                    total_cost += bybit_cost
                    total_value += bybit_value
                    lines.append(f"  <b>Bybit: {b_pnl_pct:+.2f}% (${b_pnl_usd:+,.2f})</b>")

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

        # ── الربح الإجمالي (per-exchange) ──
        dw = _fetch_all_deposits_withdrawals()
        exchange_values: list[tuple[str, float, float, float]] = []
        if BYBIT_KEY:
            bv = bybit_usdt + sum(h["value"] for h in bybit_holdings)
            bi = dw["exchanges"].get("Bybit", {})
            exchange_values.append(("Bybit", bv, bi.get("deposited", 0), bi.get("withdrawn", 0)))
        if GATE_KEY:
            gv = _fetch_gate_usdt() + sum(h["value"] for h in gate_holdings)
            gi = dw["exchanges"].get("Gate.io", {})
            exchange_values.append(("Gate.io", gv, gi.get("deposited", 0), gi.get("withdrawn", 0)))
        if KUCOIN_KEY:
            kv = _fetch_kucoin_usdt() + sum(h["value"] for h in kc_holdings)
            ki = dw["exchanges"].get("KuCoin", {})
            exchange_values.append(("KuCoin", kv, ki.get("deposited", 0), ki.get("withdrawn", 0)))

        total_val = sum(v for _, v, _, _ in exchange_values)
        total_dep = sum(d for _, _, d, _ in exchange_values)
        total_wd = sum(w for _, _, _, w in exchange_values)
        if total_dep > 0:
            lines.append(f"\n<b>━━ الربح الإجمالي ━━</b>")
            for ex_name, val, dep, wd in exchange_values:
                net_dep = dep - wd
                if net_dep > 0:
                    pnl = val - net_dep
                    pnl_pct = (pnl / net_dep) * 100
                    ic = "🟢" if pnl >= 0 else "🔴"
                    lines.append(f"  {ic} {ex_name}: ${val:,.0f} / ${net_dep:,.0f} ({pnl_pct:+.1f}%)")
                elif val > 1:
                    lines.append(f"  ⚪ {ex_name}: ${val:,.0f}")
            net = total_dep - total_wd
            overall_pnl = total_val - net
            overall_pct = (overall_pnl / net) * 100 if net > 0 else 0
            icon = "🟢" if overall_pnl >= 0 else "🔴"
            lines.append(
                f"\nإجمالي الإيداع: ${total_dep:,.2f}\n"
                f"إجمالي السحب: ${total_wd:,.2f}\n"
                f"صافي الاستثمار: ${net:,.2f}\n"
                f"القيمة الحالية: ${total_val:,.2f}\n"
                f"{icon} <b>الربح/الخسارة: {overall_pct:+.2f}% (${overall_pnl:+,.2f})</b>"
            )

        return "\n".join(lines)

    # ── أوامر / help ──
    if text in ("أوامر", "help", "/help", "مساعدة"):
        return (
            "<b>📋 الأوامر المتاحة:</b>\n\n"
            "<b>تداول (Bybit + KuCoin):</b>\n"
            "<code>فرص</code> — توصيات بيع/تعزيز + كل المنصات\n"
            "<code>بيع ربح الرمز</code> — بيع الربح فقط (حفظ رأس المال)\n"
            "<code>بيع الرمز 50%</code> — بيع 50% من عملة\n"
            "<code>بيع الرمز</code> — بيع 100%\n"
            "<i>(Gate للعرض فقط — البيع يدوي)</i>\n\n"
            "<b>الدورة التلقائية (KuCoin):</b>\n"
            "<code>دورة تشغيل</code> — تفعيل بيع الربح +10% / شراء -15%\n"
            "<code>دورة ايقاف</code> — إيقاف الدورة\n"
            "<code>دورة</code> — حالة الدورة لكل عملة\n"
            "<code>دورة هدف الرمز 50</code> — هدف ربح ثم توقف\n\n"
            "<b>محفظة:</b>\n"
            "<code>أرباح</code> — ربح/خسارة كل عملة + إجمالي\n"
            "<code>تقرير</code> — أداء كل بوت منذ التفعيل\n"
            "<code>رصيد</code> — رصيد + إيداعات/سحوبات كل المنصات\n"
            "<code>عملات</code> — العملات المحتفظ بها\n\n"
            "<b>أخرى:</b>\n"
            "<code>مراجعة</code> — مراجعة AI للعملات\n"
            "<code>حالة</code> — تقرير صحة البوتات\n"
            "<code>أوامر</code> — هذه القائمة"
        )

    return None


def _split_for_telegram(text: str, limit: int = 3900) -> list[str]:
    """Split a long message into <=limit chunks on line boundaries.

    Telegram rejects messages over 4096 chars with a 400 error and sends
    nothing — which silently breaks long reports like أرباح. Splitting on
    newlines keeps each coin block intact.
    """
    if len(text) <= limit:
        return [text]
    chunks = []
    current = ""
    for line in text.split("\n"):
        # A single line longer than the limit (rare) is hard-split.
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


def _tg_reply(chat_id: str, text: str):
    """Send a reply to a specific chat, splitting over-long messages."""
    if not NOTIFY_TOKEN:
        return
    try:
        import requests
        for chunk in _split_for_telegram(text):
            requests.post(
                f"https://api.telegram.org/bot{NOTIFY_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": chunk, "parse_mode": "HTML"},
                timeout=10,
            )
    except Exception as e:
        log(f"TG reply error: {e}")


def _command_loop():
    """Background thread: poll Telegram for commands and execute them."""
    global _tg_update_offset
    # Fail closed: with no authorized chat id, an empty NOTIFY_CHAT could match a
    # message whose chat id is missing. Refuse to run the trade interface at all.
    if not NOTIFY_CHAT:
        log("CMD: TELEGRAM_CHAT_ID غير مضبوط — واجهة الأوامر معطّلة")
        return
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

                try:
                    reply = _handle_command(text)
                    if reply:
                        _tg_reply(chat_id, reply)
                except Exception as e:
                    import traceback
                    log(f"CMD handler error for '{text[:30]}': {e}\n{traceback.format_exc()}")
                    _tg_reply(chat_id, f"❌ خطأ في تنفيذ الأمر: {e}")
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

    global _lock_fh
    _lock_fh = open(BASE_DIR / ".bot_monitor.lock", "w")
    try:
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("❌ نسخة أخرى من bot_monitor تعمل بالفعل — إيقاف")
        sys.exit(1)

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

    # KuCoin auto-cycle (profit-harvest + re-buy). Only acts when enabled
    # via the «دورة تشغيل» command — starts idle so nothing trades by surprise.
    if KUCOIN_KEY:
        cycle_thread = threading.Thread(target=_cycle_loop, daemon=True)
        cycle_thread.start()

    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            run_ai_analysis()
            held_alerts = check_held_vs_ai()
            alerts = run_checks(state)
            all_raw = []
            if held_alerts:
                sell_only = [a for a in held_alerts if "توصية بيع" in a]
                all_raw.extend(sell_only)
            if alerts:
                all_raw.extend(alerts)
            if all_raw:
                new_alerts = []
                current_hashes = set(state.last_alert_hashes[-200:]) if state.last_alert_hashes else set()
                new_hashes = list(state.last_alert_hashes[-200:]) if state.last_alert_hashes else []
                for a in all_raw:
                    h = hashlib.sha256(a.encode()).hexdigest()[:16]
                    if h not in current_hashes:
                        new_alerts.append(a)
                    current_hashes.add(h)
                    if h not in new_hashes:
                        new_hashes.append(h)
                if len(new_hashes) > 300:
                    new_hashes = new_hashes[-200:]
                state.last_alert_hashes = new_hashes
                save_state(state)
                if new_alerts:
                    ai_alerts = [a for a in new_alerts if "توصية بيع" in a]
                    sys_alerts = [a for a in new_alerts if "توصية بيع" not in a]
                    if ai_alerts:
                        notify("🔎 <b>تنبيه: AI يوصي ببيع عملات محتفظ بها</b>\n\n" + "\n\n".join(ai_alerts))
                    if sys_alerts:
                        notify("⚠️ <b>تنبيه مراقبة البوت</b>\n\n" + "\n\n".join(sys_alerts))
                    log(f"تنبيهات ({len(new_alerts)}): {[a[:40] for a in new_alerts]}")
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
