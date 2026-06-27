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
| 🔍 شناسایی ناشناس | «کی بود؟» — جواب می‌ده |
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
- `api_id` + `api_hash` از [my.telegram.org](https://my.telegram.org)
- `bot_token` از [@BotFather](https://t.me/BotFather)
- تلگرام ID خودت برای `super_admin_id`

---

## 🚀 نصب — سریع و بدون دردسر

```bash
git clone https://github.com/Noctis-Architect/puppy.git
cd puppy

bash install.sh                  # venv + پکیج + دیتابیس
sudo bash install-service.sh     # systemd — بالا بیاد بخواب
```

> ریپو: [github.com/Noctis-Architect/puppy](https://github.com/Noctis-Architect/puppy)

### دستی هم می‌شه (اگه عاشق کپی‌پیستی)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json   # پرش کن
mkdir -p data session
python main.py run
```

---

## ⚙️ config.json

```json
{
  "api_id": 12345678,
  "api_hash": "از my.telegram.org",
  "bot_token": "از BotFather",
  "super_admin_id": 123456789,
  "database_url": "sqlite+aiosqlite:///data/app.db",
  "sessions_dir": "session"
}
```

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
```

---

## 🤖 توی تلگرام

1. `/start` بزن
2. هشدار «ربات شخصی» رو بخون (بله، جدیه)
3. ثبت‌نام → شماره → کد
4. از این به بعد هرکی پیامش رو پاک کنه، تو خبر داری

**لغو ثبت‌نام:** دکمه «🚪 لغو ثبت‌نام» — سشن می‌پره، مانیتورینگ قطع می‌شه.

**ادمین:** `/admin` — آمار، لیست کاربر، حذف، فعالیت اخیر.

---

## 📁 ساختار

```
puppy/
├── app/              # مغز
├── data/             # دیتابیس (gitignore ✓)
├── session/          # سشن‌ها (gitignore ✓ — حساس!)
├── config.json       # تنظیمات (gitignore ✓)
├── install.sh
└── install-service.sh
```

---

## 🚫 commit نکن

- `config.json`
- `session/`
- `data/`
- `venv/`
- `*.zip`

---

<div align="center">

<br/>

**فوش گذاشتم با این دیتا بدزده کسی :)**

</div>
