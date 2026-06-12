# تقرير التعديلات على البوتات — مراجعة كاملة
**التاريخ:** 10-12 يونيو 2026
**الفرع:** `claude/polymarket-hedge-fund-setup-wlHTt`
**آخر كوميت:** `55c017b`

---

## ملخص عام

تم تعديل **4 ملفات** رئيسية في مجلد `vps_ready/`:

| الملف | الأسطر | طبيعة التعديل |
|-------|--------|--------------|
| `bot_monitor.py` | 2,100 سطر | إضافة ~1,266 سطر جديد (واجهة تيليجرام كاملة + 3 منصات) |
| `daytrading_bot.py` | 1,524 سطر | إصلاح 2 باقات في pipeline التعلم |
| `channel_daytrader.py` | 1,027 سطر | إصلاح باق واحد في فلتر الاتجاه |
| `monthly_channel_bot.py` | 2,292 سطر | لم يُعدّل |
| `kucoin_portfolio_bot.py` | 491 سطر | لم يُعدّل |

---

## 1. bot_monitor.py — التعديلات الرئيسية

### 1.1 واجهة أوامر تيليجرام (Telegram Command Interface)

**الآلية:** daemon thread يعمل في الخلفية يستخدم Telegram `getUpdates` (long-polling) للاستماع للرسائل.

**الدوال المضافة:**
- `_tg_get_updates()` — جلب التحديثات من تيليجرام مع offset tracking
- `_tg_reply(chat_id, text)` — إرسال رد (HTML parse mode)
- `_command_loop()` — حلقة رئيسية تعمل في daemon thread، تقبل الرسائل فقط من `TELEGRAM_CHAT_ID`
- `handle_command(text)` — معالج الأوامر الرئيسي

**الأمان:** يتحقق أن `chat_id == NOTIFY_CHAT` فقط — لا يستجيب لأي مستخدم آخر.

**الأوامر المتاحة (11 أمر):**

| الأمر | الوظيفة |
|-------|---------|
| `فرص` | مسح العملات المرتفعة من سعر الدخول، ترتيب بنسبة الربح، اقتراح بيع الربح فقط |
| `بيع ربح NEAR` | بيع نسبة الربح فقط مع الحفاظ على رأس المال الأصلي |
| `بيع ENJ 50%` | بيع نسبة محددة من عملة |
| `بيع ENJ` | بيع 100% من عملة |
| `أرباح` | عرض ربح/خسارة كل عملة من سعر الدخول (3 منصات) |
| `تقرير` | تقرير أداء كل بوت منذ بداية التشغيل |
| `رصيد` | رصيد المحفظة + إيداعات/سحوبات من كل المنصات |
| `عملات` | قائمة العملات المحتفظ بها |
| `مراجعة` | مراجعة AI للعملات المحتفظ بها مقابل توصيات البيع |
| `حالة` | تقرير صحة البوتات وحالة الخدمات |
| `رأس مال` | ضبط يدوي لرأس المال المودع والمسحوب |

### 1.2 دعم 3 منصات (Multi-Exchange Support)

#### Bybit (كانت موجودة — تم توسيعها)
- `_bybit_signed_get(endpoint)` — طلبات GET موقعة (HMAC-SHA256)
- `_bybit_signed_post(endpoint, payload)` — طلبات POST موقعة للتداول
- `_execute_sell(symbol, pct)` — تنفيذ بيع بنسبة محددة عبر Market Order
- `_execute_profit_sell(symbol)` — بيع الربح فقط (يحسب النسبة من فرق السعر)
- `_fetch_coin_balance(sym)` — جلب رصيد عملة محددة
- `_fetch_price(pair)` — جلب السعر الحالي
- `_fetch_usdt_balance()` — جلب رصيد USDT
- `_fetch_bybit_deposits_withdrawals()` — جلب الإيداعات والسحوبات (on-chain + internal)

#### Gate.io (جديد بالكامل)
- `_gate_signed_get(path)` — طلبات GET موقعة (HMAC-SHA512)
  - **ملاحظة مهمة:** التوقيع يفصل path عن query string (`/api/v4/path` + `param=value`)
  - Gate.io v4 يتطلب: `GET\n/path\nquery_string\nhashed_empty_body\ntimestamp`
- `_fetch_gate_price(sym)` — جلب السعر من Gate.io
- `_fetch_gate_usdt()` — جلب رصيد USDT
- `_fetch_gate_balances()` — جلب كل الأرصدة (فلتر > $1)
- `_get_gate_holdings_with_entry()` — الأرصدة مع أسعار الدخول من `portfolio_state.json`
- `_fetch_gate_deposits_withdrawals()` — محاولة جلب الإيداعات/السحوبات

**⚠️ قيود Gate.io:** مفتاح API الحالي read-only ولا يملك صلاحية wallet — طلبات `/api/v4/wallet/deposits` ترجع 403. **التداول معطل عمداً** على Gate.io (أمر من المالك).

#### KuCoin (جديد بالكامل)
- `_kucoin_signed_get(path)` — طلبات GET موقعة (HMAC-SHA256 + base64)
  - Passphrase أيضاً يُشفر بـ HMAC مع السر
  - يستخدم `KC-API-KEY-VERSION: "2"`
- `_fetch_kucoin_price(sym)` — جلب السعر
- `_fetch_kucoin_balances()` — جلب كل الأرصدة (فلتر > $1)
- `_get_kucoin_holdings_with_entry()` — الأرصدة مع أسعار الدخول
- `_fetch_kucoin_deposits_withdrawals()` — جلب الإيداعات/السحوبات (يعمل بنجاح)

### 1.3 تتبع رأس المال (Capital Tracking)

- `_fetch_all_deposits_withdrawals()` — يجمع من 3 منصات، أو يرجع للقيم اليدوية
- `_load_capital()` / `_save_capital()` — حفظ/قراءة القيم اليدوية من `capital_config.json`
- **الأولوية:** API أولاً → fallback يدوي إذا API رجعت $0
- **ملف التخزين:** `~/bots/capital_config.json`

### 1.4 نظام البيع الذكي (Smart Sell)

- `_scan_profitable_coins()` — يمسح كل عملات Bybit، يرتبها بنسبة الربح من سعر الدخول
- **حساب بيع الربح فقط:** `sell_pct = (current_price - entry_price) / current_price * 100`
  - مثال: دخول $1.00، حالي $1.50 → بيع 33.3% يحافظ على رأس المال الأصلي
- `_execute_profit_sell(symbol)` — ينفذ البيع بالنسبة المحسوبة

### 1.5 قراءة المراكز من كل البوتات (Cross-Bot Position Reading)

- `get_all_held_coins()` — يقرأ من 3 ملفات state لمعرفة العملات المحتفظ بها
- `get_all_positions()` — يقرأ سعر الدخول والكمية من كل بوت

**ملفات الحالة المقروءة:**

| الملف | المفتاح | صيغة الدخول | صيغة الكمية |
|-------|---------|------------|------------|
| `monthly_state.json` | `open_positions["SYM/USDT"]` | `pos["entry"]` | `pos["qty"]` |
| `daytrading_state.json` | `positions["SYMUSDT"]` | `pos["entry_price"]` | `pos["qty"]` |
| `channel_daytrader_state.json` | `positions["SYM"]` | `pos["entry_price"]` | `pos["qty"]` |
| `portfolio_state.json` | `entry_prices["SYM@Exchange"]` | القيمة مباشرة | — |

### 1.6 فلترة العملات الوهمية (Stale Coin Filter) — آخر تعديل

**المشكلة:** `monthly_state.json` يحتوي على مراكز قديمة (DUSK, NIL, PHA, TAO, WARD) رصيدها $0 في المنصة لكنها لا تزال مسجلة كـ "مراكز مفتوحة".

**الحل:** أوامر `رصيد` و`أرباح` و`فرص` الآن تتحقق من الرصيد الحقيقي في Bybit API وتتجاهل أي عملة قيمتها < $1.

**التعديلات:**
- `رصيد`: سطر 1712 — `if val < 1.0: continue`
- `أرباح`: أسطر 1803-1808 — جلب `_fetch_coin_balance()` الحقيقي بدل الاعتماد على `qty` من الـ state
- `فرص` (`_scan_profitable_coins`): نفس المنطق — تحقق من الرصيد الفعلي + تحديث `qty` بالرصيد الحقيقي

### 1.7 متغيرات البيئة المطلوبة (.env_monthly)

```
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...
CEREBRAS_API_KEY=...
GEMINI_API_KEY=...
BYBIT_API_KEY=...
BYBIT_API_SECRET=...
GATE_API_KEY=...
GATE_API_SECRET=...
KUCOIN_API_KEY=...
KUCOIN_API_SECRET=...
KUCOIN_PASSPHRASE=...
```

---

## 2. daytrading_bot.py — إصلاح باقين

### 2.1 فلتر Score المزدوج (سطر 616)

**المشكلة:** فلتر أولي `score < 58` يحذف العملات قبل تطبيق memory boost. العملات بسكور 50-57 لا تصل أبداً لـ memory boost الذي يمكن أن يرفعها فوق 62.

**قبل:**
```python
if score < 58:
    continue
```

**بعد:**
```python
if score < 50:
    continue
```

**التأثير:** العملات بسكور 50-57 الآن تمر للمرحلة التالية حيث memory boost (من الصفقات السابقة الناجحة) يمكن أن يرفعها فوق العتبة النهائية 62.

### 2.2 عدم مسح Streak يومياً (في `roll_day()`)

**المشكلة:** `st.streak` (عداد الخسائر/الأرباح المتتالية لكل عملة) لم يُمسح عند تغيير اليوم. خسائر أمس تعاقب عملات اليوم.

**الإضافة في `roll_day()`:**
```python
st.streak = {}
```

---

## 3. channel_daytrader.py — إصلاح باق واحد

### 3.1 فلتر الاتجاه لا يحظر فشل API (سطر 678)

**المشكلة:** `_coin_trend_up()` ترجع `None` عند فشل API. الكود كان:
```python
if trend is False:
    # لا تشتري
```
`None is False` = `False` → فشل API يُعامل كـ "لا يوجد اتجاه هابط" → يسمح بالشراء!

**بعد:**
```python
if trend is not True:
    # لا تشتري
```

**التأثير:** أي فشل في API الآن يمنع الشراء (fail-closed بدل fail-open).

---

## 4. ملفات لم تُعدّل

| الملف | السبب |
|-------|-------|
| `monthly_channel_bot.py` (2,292 سطر) | البوت الشهري — لم يُطلب تعديله |
| `kucoin_portfolio_bot.py` (491 سطر) | بوت مراقبة read-only — يعمل بشكل سليم |

---

## 5. البنية على السيرفر

```
~/bots/
├── .env_monthly                     # كل مفاتيح API
├── bot_monitor.py                   # مراقب + واجهة تيليجرام + تداول
├── daytrading_bot.py                # بوت تداول يومي (Bybit)
├── channel_daytrader.py             # بوت تداول يومي من قنوات تيليجرام (Bybit)
├── monthly_channel_bot.py           # بوت شهري من قنوات تيليجرام (Bybit)
├── kucoin_portfolio_bot.py          # مراقب محفظة (3 منصات، read-only)
├── monthly_state.json               # حالة البوت الشهري
├── daytrading_state.json            # حالة بوت التداول اليومي
├── channel_daytrader_state.json     # حالة بوت القنوات اليومي
├── portfolio_state.json             # أسعار دخول من kucoin_portfolio_bot
├── capital_config.json              # رأس مال يدوي (اختياري)
├── monitor_state.json               # حالة المراقب الداخلية
└── monitor.log                      # لوق المراقب
```

---

## 6. مشاكل معروفة ولم تُحل

| المشكلة | السبب | الحل المقترح |
|---------|-------|-------------|
| Bybit deposits API ترجع $0 | مفتاح API قد لا يملك صلاحية "Assets"، أو الإيداعات كانت عبر fiat gateway | إنشاء مفتاح API جديد بصلاحية Assets |
| Gate.io wallet API ترجع 403 | مفتاح API read-only بدون صلاحية wallet | إنشاء مفتاح بصلاحية wallet (أو تجاهل — المنصة للمشاهدة فقط) |
| `monthly_state.json` يحتوي مراكز وهمية | البوت الشهري لا يمسح المراكز المباعة/المهجورة بشكل كامل | تمت معالجتها بفلتر < $1 في العرض، لكن المراكز لا تزال في الملف |
| رأس المال الفعلي غير معروف | المالك لا يتذكر إجمالي الإيداعات والسحوبات | انتظار مراجعة كشف الحساب من المنصات |

---

## 7. تسلسل الكوميتات (من الأقدم للأحدث)

```
df0d1dc  واجهة أوامر تيليجرام للتداول عن بعد
171c915  أمر أرباح — ربح/خسارة كل عملة من سعر الدخول
9ce5558  إضافة أرباح Gate.io
127ab51  إضافة Gate.io API للأرصدة الحية
6c5073b  إضافة KuCoin API للأرصدة والأرباح
4a133bc  حساب الربح الإجمالي بناء على الإيداعات/السحوبات
6018ec2  جلب الإيداعات/السحوبات تلقائياً من 3 منصات
ef4d505  إصلاح توقيع Gate.io API + رصيد USDT
8aa7e8a  إضافة Bybit internal deposits + fallback يدوي
c6f28f6  إصلاح pipeline التعلم: score filter + streak reset + trend fail-closed
a9c1619  أمر تقرير — أداء كل بوت منذ التفعيل
18603ab  نظام البيع الذكي — مسح العملات المرتفعة + بيع الربح فقط
55c017b  فلترة العملات الوهمية ($0) من التقارير
```

---

## 8. ملاحظات أمنية مهمة

1. **Gate.io للمشاهدة فقط** — لا يوجد كود تداول لـ Gate.io (أمر من المالك)
2. **التداول فقط عبر Bybit** — أوامر `بيع` و `بيع ربح` تعمل على Bybit حصراً
3. **مفاتيح API في `.env_monthly` على السيرفر فقط** — لا تُرفع على GitHub
4. **وقف الخسارة 999% متعمد** — لا يُعدّل (قرار المالك)
5. **bot_monitor يقبل أوامر فقط من `TELEGRAM_CHAT_ID`** — أي chat_id آخر يُتجاهل

---

## 9. كيفية مراجعة الكود

```bash
# استعراض كل التعديلات
git log --oneline df0d1dc~1..55c017b

# استعراض diff كامل
git diff df0d1dc~1..55c017b -- vps_ready/

# استعراض ملف محدد
git diff df0d1dc~1..55c017b -- vps_ready/bot_monitor.py
git diff c6f28f6~1..c6f28f6 -- vps_ready/daytrading_bot.py
git diff c6f28f6~1..c6f28f6 -- vps_ready/channel_daytrader.py
```
