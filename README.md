# 🎮 Marceline // The Elite Gaming Group Manager 👾

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Database-PostgreSQL-red?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Deployed%20on-Heroku-purple?style=for-the-badge&logo=heroku&logoColor=white" />
  <img src="https://img.shields.io/badge/Vibe-Cute%20but%20Savage-pink?style=for-the-badge" />
</p>

---

### **"I track your wins, roast your losses and remember everything you're too lazy to save. Built with caffeine and logic ☕️💻"**

**Marceline** is a basic Telegram bot designed to manage competitive gaming groups. She helps you start play sessions, ping everyone, store fun stuff, and track match stats — all per-group with persistent storage.
.

---

## 🔥 Key Features

### 🕹 Gaming & Stats Engine
* **Dynamic Sessions:** Automated 1v1 and 2v2 RSVP setups with `In`, `Out`, and `Pending` logic.
* **Real-Time Leaderboards:** Monthly and Overall rankings based on win percentage (min. 3 matches).
* **Player Analytics:** Detailed profiles showing head-to-head records and your "Favorite Opponent".

### 🔐 The Vault
* **Keyword Persistence:** Save text, media, or stickers for instant recall using custom keywords.
* **The Excuse Database:** A specialized storage system for your best reasons why the "ping was too high".

### 📣 Group Logic
* **Smart Mentions:** A custom `/all` system that respects user exclusion lists.
* **Savage Roasts:** A community-driven roast engine where users can contribute their own lethal lines.

---

## 🛠 Tech Stack
* **Language:** Python 3.10+
* **Framework:** `python-telegram-bot`
* **ORM:** SQLAlchemy with Heroku Postgres
* **Deployment:** Optimized for Heroku Worker dynos with a persistent database layer

---

## 💻 Local Development

1. ## **Clone & Environment:**
   
   ```bash
   git clone [https://github.com/Doom098/marceline-bot.git](https://github.com/Doom098/marceline-bot.git)
   cd marceline-bot
   python -m venv venv
   source venv/bin/activate  # venv\Scripts\activate on Windows

2. ## **Environment Isolation:**  
   **Create a virtual environment to prevent dependency conflicts**
   
   ```bash
   # Windows
    python -m venv venv
    venv\Scripts\activate

   # Linux/Mac
    python3 -m venv venv
    source venv/bin/activate

  3. ## **Dependency Injection:**
     ** Install all required libraries, including `python-telegram-bot` and `SQLAlchemy`**

     ```bash
     pip install -r requirements.txt

  4. ## **Configuration:**  
     **Rename `.env.sample` to `.env` and insert your credentials. Ensure this file is in your `.gitignore`.

  5. ## **Launch the System:**   
     **Launch the main script to wake up Marceline**

     ```bash
     python main.py
     

   
   

  
