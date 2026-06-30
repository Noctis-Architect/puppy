<div align="center">

# 🛡 Message Guard

### ربات شخصی تلگرام — «پیام حذف شد؟ نه عزیزم، اینجاست»

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Telethon](https://img.shields.io/badge/Telethon-Userbot-0088CC?style=flat-square&logo=telegram&logoColor=white)](https://github.com/LonamiWebs/Telethon)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-26A5E4?style=flat-square&logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![Self-Hosted](https://img.shields.io/badge/Self--Hosted-Personal-2EA043?style=flat-square)]()
[![GitHub](https://img.shields.io/badge/GitHub-Noctis--Architect%2Fpuppy-181717?style=flat-square&logo=github)](https://github.com/Noctis-Architect/puppy)

*طرف مقابل پیامش رو پاک کرد؟ تو همون لحظه یه «ها ها، گرفتمت» می‌گیری.*

<br/>

> ## 🔒 ربات **شخصی**ه — نه SaaS، نه فیلترشکن رایگان
>
> این پروژه برای **سرور خودت** ساخته شده. سشن، شماره، پیام خصوصی — همه‌چی روی **همون ماشینی** می‌مونه که تو صاحبش هستی.
>
> ### ⛔ تو رباتِ بقیه شماره نده. جدی‌ام.

</div>



---

## ✨ چیکار می‌کنه؟

| قابلیت | یعنی چی |
|--------|---------|
| 📥 آرشیو پیام | پیام خصوصی میاد → ذخیره می‌شه |
| 🗑 هشدار حذف | پاکش کرد؟ → برات می‌فرسته |
| ✏️ ردیاب ادیت | پیام ویرایش شد؟ → نسخهٔ قبل و بعد |
| 🔍 شناسایی ناشناس | «کی بود؟» — جواب می‌ده (دستی + خودکار) |
| 👥 ابزار گروه | ردیابی فرد، گروه‌های تحت‌نظر، منشن و عضو جدید |
| 🔎 جستجو و اکسپورت | جستجو در آرشیو، پروفایل مخاطب، خروجی مکالمه |
| ⏰ اتوماسیون | پیام زمان‌بندی‌شده و یادآور |
| 👁 ردیاب مخاطب | آنلاین/آفلاین و تغییرات پروفایل |
| ⚙️ تنظیمات | هر قابلیت روشن/خاموش — حالت «نیستم»، بکاپ پیام خودت |
| 🎁 سیستم معرف | کد معرف بده، دوست بیار |
| 🛡 پنل ادمین | کاربرا رو ببین، حذف کن، آمار بگیر |
| 🚪 لغو ثبت‌نام | پشیمون شدی؟ سشن رو بسوزون برو |

---

## 🔐 قانون طلایی

1. **سرور خودت** → نصب کن
2. **سرور بقیه** → دست نزن، شماره نده، کد نده
3. `session/` = کلید خونه‌ات. لو بره = تموم
4. `config.json` = توکن بات. commit نکن مگر اینکه دوست داشته باشی هکرا مهمونت باشن

---

## 📋 چی لازمه؟

- لینوکس (دیبیاَن/اوبونتو — آره، ویندوز نه)
- Python 3.11+
- `bot_token` از [@BotFather](https://t.me/BotFather)
- (`api_id` + `api_hash` در `config.example.json` از قبل تنظیم شده — نیازی به my.telegram.org نیست)
- تلگرام ID خودت برای `super_admin_id`

---

## 🚀 نصب — یک خط

فقط اسکریپت نصب را از GitHub بگیر؛ **خودش کل پروژه را دانلود و نصب می‌کند**:

```bash
curl -fsSL https://raw.githubusercontent.com/Noctis-Architect/puppy/main/install.sh | bash
```

پیش‌فرض نصب در `~/puppy` است. مسیر دیگر:

```bash
PUPPY_INSTALL_DIR=/opt/puppy curl -fsSL https://raw.githubusercontent.com/Noctis-Architect/puppy/main/install.sh | bash
```

**سرویس systemd** (یک‌بار بعد از نصب):

```bash
sudo bash ~/puppy/install-service.sh
```

---

## 🔄 به‌روزرسانی — همان یک خط

`config.json`، `session/`، `data/` و `media/` **دست نخورده** می‌مانند؛ اگر سرویس نصب باشد خودکار restart می‌شود:

```bash
curl -fsSL https://raw.githubusercontent.com/Noctis-Architect/puppy/main/install.sh | bash -s -- -u
```

یا از روی سرور (بدون دانلود دوباره):

```bash
bash ~/puppy/install.sh -u
```

---

## 🛠 نصب دستی (اختیاری — برای توسعه‌دهندگان)

```bash
git clone https://github.com/Noctis-Architect/puppy.git
cd puppy && bash install.sh --fresh
```

> ریپو: [github.com/Noctis-Architect/puppy](https://github.com/Noctis-Architect/puppy)

---

## ⚙️ config.json

```json
{
  "api_id": 27758062,
  "api_hash": "از قبل در config.example.json",
  "bot_token": "از BotFather",
  "super_admin_id": 123456789,
  "database_url": "sqlite+aiosqlite:///data/app.db",
  "sessions_dir": "session",
  "media_dir": "media",
  "proxy": {
    "type": "",
    "host": "",
    "port": 0
  },
  "cleanup": {
    "hour": 3,
    "minute": 0,
    "timezone": "Asia/Tehran",
    "retention_days": 90
  },
  "monitoring": {
    "unread_scan_interval_seconds": 60
  },
  "logging": {
    "level": "INFO"
  }
}
```

| بخش | توضیح |
|-----|--------|
| `media_dir` | محل ذخیرهٔ مدیا (مثلاً view-once) |
| `cleanup` | زمان و مدت نگهداری پیام‌ها در دیتابیس |
| `monitoring` | فاصلهٔ اسکن پیام‌های خوانده‌نشده |
| `proxy` | اختیاری — SOCKS5/MTProto برای اتصال Telethon |

---

## 🖥 دیباگ و مدیریت

```bash
# وضعیت سرویس
sudo systemctl status puppy

# ری‌استارت
sudo systemctl restart puppy

# لاگ زنده — وقتی چیزی خراب شد اینجا می‌فهمی
sudo journalctl -u puppy -f

# اجرای دستی (برای دیباگ)
git clone https://github.com/Noctis-Architect/puppy.git ~/puppy
cd ~/puppy
source venv/bin/activate
python main.py run

# CLI
python main.py list-users
python main.py add-user
python main.py deactivate-user <id>
python main.py activate-user <id>
```

---

## 🤖 توی تلگرام

1. `/start` بزن
2. هشدار «ربات شخصی» رو بخون (بله، جدیه)
3. ثبت‌نام → شماره → کد
4. از این به بعد هرکی پیامش رو پاک کنه، تو خبر داری

**منوی ثبت‌نام‌شده:** آرشیو حذف‌شده‌ها، شناسایی ناشناس، جستجو، تنظیمات، ابزار گروه، اتوماسیون و بقیه — از کیبورد بات.

**لغو ثبت‌نام:** دکمه «🚪 لغو ثبت‌نام» — سشن می‌پره، مانیتورینگ قطع می‌شه.

**ادمین:** `/admin` — آمار، لیست کاربر، حذف، فعالیت اخیر. دستورات CLI: `/stats`، `/users`، `/user <id>`، `/delete <id>`.

---

## 📁 ساختار

```
puppy/
├── app/
│   ├── core/           # بارگذاری ماژول‌ها (loader، module_api)
│   ├── modules/        # قابلیت‌ها — هر پوشه یک BotModule
│   │   ├── registration/   # ثبت‌نام و لغو
│   │   ├── archive/          # آرشیو، حذف، اسکن، پاکسازی
│   │   ├── settings/         # تنظیمات کاربر
│   │   ├── anonymous_reveal/ # شناسایی پیام ناشناس
│   │   ├── group_tools/      # گروه و ردیابی فرد
│   │   ├── message_intel/    # ردیاب ادیت
│   │   ├── contact_tracking/ # آنلاین و پروفایل
│   │   ├── memory_search/    # جستجو، اکسپورت، خلاصه روزانه
│   │   ├── automation/       # زمان‌بندی و یادآور
│   │   └── admin/            # پنل ادمین
│   ├── bot/            # میان‌افزار، کیبورد، امنیت
│   ├── db/             # مدل‌های پایه و سشن SQLAlchemy
│   ├── telegram/       # Telethon — اتصال و pool
│   └── runtime.py      # نقطهٔ ورود سرویس
├── data/               # دیتابیس (gitignore ✓)
├── media/              # فایل‌های مدیا (gitignore ✓)
├── session/            # سشن‌ها (gitignore ✓ — حساس!)
├── config.json         # تنظیمات (gitignore ✓)
├── install.sh
└── install-service.sh
```

ماژول‌ها به‌صورت خودکار از `app/modules/` کشف می‌شن؛ هر کدام می‌تونه router بات، رویداد Telethon، job زمان‌بندی‌شده و migration سبک داشته باشه.

---

## 🚫 commit نکن

- `config.json`
- `session/`
- `data/`
- `media/`
- `venv/`
- `*.zip`

---

<div align="center">

<br/>

**فوش گذاشتم با این دیتا بدزده کسی :)**

</div>
