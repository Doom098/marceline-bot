# 🎮 Marceline // The Elite Gaming Group Manager 👾

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Database-SQLAlchemy-red?style=for-the-badge&logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/Deployed%20on-Heroku-purple?style=for-the-badge&logo=heroku&logoColor=white" />
  <img src="https://img.shields.io/badge/Vibe-Cute%20but%20Savage-pink?style=for-the-badge" />
</p>

---

### **"I don't have a heart, just a script that’s significantly better at gaming than you."**

**Marceline** is a high-performance Telegram bot designed to manage competitive gaming groups. Developed by **[@doomxragnar](https://t.me/doomxragnar)**, she doesn't just manage chats—she judges them. Whether it's tracking your ELO, archiving your stickers, or roasting your 0-10 win streak, Marceline is the only system you need.

---

## 🔥 Key Features

### 🕹 Gaming & Stats Engine
* **Dynamic Matchmaking:** Automated 1v1 and 2v2 session setups with interactive RSVP buttons (`In`, `Out`, `Pending`).
* **Real-Time Leaderboards:** Monthly and Overall rankings based on win percentage.
* **Player Profiles:** Detailed head-to-head stats and "Favorite Opponent" calculations.
* **Auto-Cleanup:** Expired sessions are automatically wiped every 6 hours to keep your chat clean.

### 🔐 The Vault (Persistence Layer)
* **Media Archiving:** Save text, photos, or videos with custom keywords for instant recall.
* **Sticker Management:** Dedicated storage for the group's best (and worst) stickers.
* **The Excuse Database:** A random-access collection of your best excuses for why the ping was "too high".

### 📣 Group & Admin Logic
* **Smart Mentions:** Custom `/all` pings that exclude users who have opted out.
* **Savage Roasts:** A custom-built roast engine with the ability for users to contribute their own lines.
* **Admin Control:** Dynamic DM menu management and group-specific "About" configuration.

---

## 🛠 Tech Stack

* **Language:** Python 3.10+
* **Framework:** `python-telegram-bot`
* **ORM/DB:** SQLAlchemy with SQLite/PostgreSQL support.
* **Deployment:** Optimized for Heroku workers with a persistent database layer.

---

## 🚀 Installation & Deployment

### 1. Clone the logic
```bash
git clone [https://github.com/Doom098/marceline-bot.git](https://github.com/Doom098/marceline-bot.git)
cd marceline-bot
