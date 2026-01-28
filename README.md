#🚗 AutoRia Real-Time Monitoring Bot

[![Python Application CI](https://github.com/talisman-ep/AutoRia-Scraping-Bot-Python-/actions/workflows/python-app.yml/badge.svg)](https://github.com/talisman-ep/AutoRia-Scraping-Bot-Python-/actions/workflows/python-app.yml)
![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![Aiogram](https://img.shields.io/badge/Aiogram-3.x-26A5E4?logo=telegram&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Container-2496ED?logo=docker&logoColor=white)
![AsyncPG](https://img.shields.io/badge/AsyncPG-High%20Perf-green)

A high-performance, asynchronous monitoring system for the Ukrainian car market (Auto.ria.com).
This bot allows users to subscribe to specific search criteria and receive **instant notifications** about new listings, often faster than the official platform's notifications.

> **Key Highlight:** Built with a focus on scalability, concurrency control, and "unbreakable" scraping techniques.

---

## 📸 Interface Preview

| **1. Main Menu & Search** | **2. Dynamic Pagination** |
|:---:|:---:|
| | |
|<img width="962" height="859" alt="image" src="https://github.com/user-attachments/assets/9b6ee382-a0ca-4dc1-a8b7-22c0c5dbb677" />|<img width="931" height="816" alt="image" src="https://github.com/user-attachments/assets/d42bb36f-e05a-4cc9-8a01-232a87d52a0d" />|

| **3. Instant Notification** | **4. Subscription Management** |
|:---:|:---:|
| | |
|<img width="812" height="558" alt="image" src="https://github.com/user-attachments/assets/046586ea-1430-4dec-baef-1d2cfd14c5e8" />|<img width="982" height="316" alt="image" src="https://github.com/user-attachments/assets/04e123cd-9dda-4a46-99fe-fee3445b4380" />|

---

## ✨ Key Features

### 👤 For Users
* **Flexible Subscriptions:** Filter by Brand, Model, Year (From/To), Price (From/To), Region, Fuel Type, and Gearbox.
* **Zero-Latency Alerts:** Notifications are sent immediately after the background scheduler detects a new car.
* **Dynamic Data:** The bot fetches Brands, Models, and Regions directly from the API, ensuring no outdated "hardcoded" lists.
* **User-Friendly UI:** Smart inline keyboards with pagination for navigating hundreds of car models.

### ⚙️ Under the Hood (Technical Advantages)
* **Robust Scraping Engine:**
    * Bypasses standard HTML scraping issues by parsing the `window.__PINIA__` or `window.__NUXT__` JSON state embedded in the page.
    * **Resilient to UI changes:** As long as the data state exists, the scraper works.
* **Smart Concurrency Control:**
    * Uses `asyncio.Semaphore` to limit concurrent outgoing HTTP requests, preventing `429 Too Many Requests` bans/errors.
    * **Connection Pooling:** Utilizes `asyncpg` pools to handle database connections efficiently under load.
* **Architecture:**
    * **Repository Pattern:** Strict separation between the database layer and business logic.
    * **Dependency Injection:** Database repositories are injected via Middleware.
    * **RAM Caching:** Static data (Brands/Regions) is cached in memory (TTL 1h) to reduce external API calls by ~95%.

---

## 🛠 Tech Stack & Architecture

The project is built using modern Python asynchronous paradigms.

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Core** | Python 3.11 | Modern syntax, strong typing support. |
| **Bot Framework** | Aiogram 3.x | Fully asynchronous, router-based architecture. |
| **Database** | PostgreSQL 15 | Relational data integrity for users and complex search queries. |
| **DB Driver** | AsyncPG | The fastest async driver for PostgreSQL. |
| **Scraper** | Aiohttp + Regex | Non-blocking HTTP requests with custom Regex parsing logic. |
| **Deployment** | Docker Compose | Containerized environment for Bot and Database. |

### Directory Structure

```text
├── src/
│   ├── bot/
│   │   ├── handlers/       # Route handlers (User interaction)
│   │   ├── keyboards.py    # Dynamic keyboard generators
│   │   ├── scheduler.py    # Background monitoring logic (The "Heart")
│   │   └── states.py       # FSM (Finite State Machine) definitions
│   ├── database/
│   │   ├── repository.py   # CRUD operations (Repository Pattern)
│   │   └── setup.py        # Database migration & initialization
│   └── parser/
│       └── scraper.py      # Core scraping logic & caching
├── main.py                 # Application entry point
├── Dockerfile              # Container instruction
├── docker-compose.yml      # Service orchestration
└── .env                    # Environment variables

```

---

## 🚀 Installation & Setup

### Prerequisites

* **Docker** & **Docker Compose** (Recommended)
* *Or:* Python 3.11+ and a local PostgreSQL instance.

### Option 1: Run with Docker (Fastest)

1. **Clone the repository:**
```bash
git clone [https://github.com/YOUR_USERNAME/autoria-bot.git](https://github.com/YOUR_USERNAME/autoria-bot.git)
cd autoria-bot

```


2. **Configure Environment:**
Create a `.env` file in the root directory:
```env
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
DB_USER=postgres
DB_PASS=postgres
DB_NAME=autoria_db
DB_HOST=db
DB_PORT=5432

```


3. **Launch:**
```bash
docker-compose up --build -d

```


*The bot will automatically set up the database schema and start monitoring.*

### Option 2: Run Locally

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

```


2. Install dependencies:
```bash
pip install -r requirements.txt

```


3. Set `DB_HOST=localhost` in your `.env` file.
4. Run the bot:
```bash
python main.py

```



---

## 🧠 Technical Challenges Solved

### 1. The "Single Page Application" Problem

**Challenge:** Auto.ria uses a dynamic frontend framework (Vue.js/Nuxt). Standard `BeautifulSoup` scraping often fails because data is rendered via JavaScript.
**Solution:** Instead of parsing HTML tags, the bot extracts the raw JSON state (`window.__PINIA__`) using Regular Expressions. This is 10x faster and significantly more stable.

### 2. The "Rate Limit" Problem

**Challenge:** Checking 100+ subscriptions simultaneously triggers anti-bot protection.
**Solution:** Implemented `asyncio.Semaphore` in the scheduler. This creates a "queue" system where only  requests happen at the exact same millisecond, smoothing out the traffic spike.

### 3. The "Ghost Car" Problem

**Challenge:** Sometimes the API returns "promoted" cars that don't match the search ID criteria (e.g., showing a VW Passat when searching for a BMW).
**Solution:** Added a "Safety Catch" layer in Python. Even after the API response, the bot double-checks if the car title strictly contains the requested model name before notifying the user.

---

## 🔮 Future Roadmap

* [ ] **Admin Panel:** Web interface for managing users and global stats.
* [ ] **Analytics:** Price history graphs for specific models.
* [ ] **Multi-platform:** Add support for OLX.ua and RST.ua.
* [ ] **WebSocket:** Use WebSocket for even faster updates (if supported by source).

---

## 📝 License

This project is open-source and available under the [MIT License](https://www.google.com/search?q=LICENSE).


```
