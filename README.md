
# 🚗 Self Booking Bot (Enhanced)

An automated bot built to help secure hard-to-get slots from (CDC), with a focus on **automation, speed, and cloud deployment (no local machine required)**.

This project is based on:
- cdc-helper by mfjkri  
- cdc-bot by Zhannyhong  
where I forked this repository from.

Refactored and enhanced with additional features and improvements.

---

## ⚡ Features

- 🔄 Periodically checks for available sessions:
  - Simulator
  - Practical Lessons
  - BTT / RTT / FTT
  - Practical Test
- 🤖 Automatically solves CAPTCHAs (via 2Captcha)
- 📊 Compares against your booked sessions
- ⏱ Detects earlier available slots
- 📲 Sends instant notifications via Telegram
- ⚡ Attempts to reserve earlier slots automatically
- ☁️ Designed to run on cloud (24/7 automation)

---

## ⚠️ Disclaimer

**Use at your own risk.**

ComfortDelGro Driving Centre may detect automated behaviour.  
Possible consequences include:
- Temporary account suspension
- Stored value disabled (~5 days)
- Login restrictions

Detection may be based on:
- Request frequency
- Timing patterns
- CAPTCHA interaction

This version includes improvements to reduce detection risk, but there are **no guarantees**.

---

## 🧠 Improvements in This Version

- ☁️ Cloud-ready (no need to run on local machine)
- 🔁 Improved scheduling logic
- 🔐 Environment variable support (no hardcoded credentials)
- 📉 Reduced detection patterns (optional random delays)
- 📲 Telegram-first notification system
- 🧹 Cleaner and more modular code structure

---

## 🛠 Requirements

- Python 3.9+
- Google Chrome or Firefox
- 2Captcha account

Install dependencies:

```bash
pip install -r requirements.txt
````

---

## ⚙️ Setup

### 1. Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

---

### 2. Environment Variables

Set the following variables (recommended instead of editing config directly):

```bash
CDC_USERNAME=your_username
CDC_PASSWORD=your_password
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
TWOCAPTCHA_API_KEY=your_key
```

---

### 3. 2Captcha Setup

* Create an account at [https://2captcha.com](https://2captcha.com)
* Add credits
* Copy your API key into your config or environment variables

---

### 4. Telegram Bot Setup

1. Create a bot using BotFather
2. Copy your bot token
3. Send `/start` to your bot
4. Open:

   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
5. Get your `chat_id` and set it in your config

---

## 🚀 Running the Bot

### Local (for testing)

```bash
python src/main.py
```

---

### Cloud (Recommended)

Deploy using:

* Railway
* Render
* VPS

This allows:

* 24/7 runtime
* No need to keep your computer on
* More stable execution

---

## ⏱ Default Behaviour

* Runs every ~30 minutes
* Skips 3AM – 6AM (low activity period)
* Can be modified for random intervals to reduce detection

---

## 📲 Notifications

You will receive Telegram alerts for:

* Earlier slots found
* Reserved sessions
* Booking updates
* Errors or crashes

---

## 📁 Project Structure

```
src/
 ├── main.py
 ├── website_handler/
 ├── utils/
 │    ├── notifications/
 │    ├── captcha/
 │    ├── log.py
abstracts/
config/
logs/
```

---

## 🧪 Known Limitations

* CDC website updates may break selectors
* CAPTCHA solving is not always 100% reliable
* Bot detection is still possible
* Some course types may not be fully supported

---

## 💡 Future Improvements

* Mobile app automation (lower CAPTCHA detection)
* Smarter booking prioritisation
* Fully async execution
* Monitoring dashboard
* Targeted slot booking

---


## 📌 Final Notes

This bot is intended to:

* Save time
* Improve booking chances

Use responsibly.

```

Just tell me 👍
```
