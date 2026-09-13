# 🤖 Production Telegram Video Automation Bot

A production-ready, modular Python automation system that monitors authorized cloud storage (including TeraBox via official developer APIs, local disk, and S3-compatible stores), detects new media files, extracts and enriches metadata using movie databases (TMDB/OMDB), prevents duplicate postings via content hashing and file IDs, and publishes rich, formatted posts with inline "▶ WATCH VIDEO" buttons to Telegram channels and user-facing bot interfaces.

---

## 🏗 System Architecture

```
Authorized Cloud Storage / TeraBox (Official Open Platform)
                        ↓
                New File Detector
                        ↓
                  Sync Service
                        ↓
            Filename & Metadata Processor
                        ↓
              Multi-Tier Duplicate Checker
                        ↓
              Async SQLite Database
                        ↓
             Telegram Bot & Rate Limiter
                        ↓
                 Telegram Channel
```

---

## 🌟 Key Features

- **Strict Rights & Compliance First**: Operates exclusively with public domain, user-owned, or authorized distribution media. TeraBox is accessed strictly through official developer APIs (no credential scraping or unofficial bypasses). Video binaries are never directly uploaded to Telegram unless explicitly permitted (`ENABLE_DIRECT_VIDEO_UPLOAD=false`).
- **Extensible Storage Abstraction**: Clean `StorageProvider` interface supporting:
  - `LocalStorageProvider`: For self-hosted media directories and NAS mounts.
  - `TeraBoxProvider`: Official Open Platform REST client (`/file/list`, `/file/detail`, `/share/create`).
  - `S3StorageProvider`: AWS S3, MinIO, Cloudflare R2, Backblaze B2.
- **Intelligent Filename Parser**: Extracts title, release year, video resolution (`4K UHD`, `1080p`, `720p`), audio codec, and release source, while stripping scene noise tags.
- **Metadata Enrichment (TMDB & OMDB)**: Fetches official high-res posters, release year, genres, IMDb/TMDB rating, and synopses with graceful local fallback.
- **Multi-Tier Duplicate Prevention**: Dual-verification using unique `storage_file_id` and streamed SHA-256 `content_hash`.
- **Telegram Bot & Channel Publisher**:
  - Exact requested post template layout with poster photo support.
  - Inline `[▶ WATCH VIDEO]` button pointing directly to authorized storage share URL.
  - Automatic retry with exponential backoff and flood control (`RetryAfter`) handling.
- **Bot Commands**:
  - **User**: `/start`, `/help`, `/latest`, `/search <title>`
  - **Admin**: `/admin`, `/stats`, `/resync`, `/delete <msg_id>`, and interactive `/add` staging workflow.
- **Background Scheduler**: Async APScheduler for periodic sync runs without blocking the bot.
- **Production Healthcheck & Webhook API**: Built-in FastAPI/uvicorn server on port `8080` exposing `/health` for container orchestration and `/webhook/storage` for real-time cloud upload notifications.
- **Docker & VPS Ready**: Multi-stage lightweight Docker image, `docker-compose.yml`, and systemd unit instructions.

---

## 📋 Exact Telegram Post Layout

```
🎬 {TITLE}

📅 Year: {YEAR}
🎭 Genre: {GENRE}
⭐ Rating: {RATING}
🎞 Quality: {QUALITY}

📝 {DESCRIPTION}

[▶ WATCH VIDEO] (Inline Button)
```

---

## 🚀 Quick Start (Local Setup)

### 1. Prerequisites
- Python 3.11 or 3.12
- Git
- Telegram account

### 2. Clone and Setup Environment
```bash
git clone <repository_url>
cd bot

# Create Python virtual environment
python -m venv .venv

# Activate environment:
# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# Install production dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Open `.env` and configure your credentials:
```env
# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_1234567
TELEGRAM_CHANNEL_ID=@your_channel_name
ADMIN_USER_IDS=123456789,987654321

# Storage (e.g. local)
STORAGE_PROVIDER=local
LOCAL_STORAGE_PATH=./media_storage
LOCAL_STORAGE_BASE_URL=https://storage.example.com/videos

# Metadata (optional but recommended)
TMDB_API_KEY=your_tmdb_api_key
```

### 4. Run the Bot
```bash
python main.py
```

To run a single sync pass from CLI without starting the Telegram bot server:
```bash
python main.py --sync-only
```

---

## 🧪 Running Unit Tests

Run the complete test suite with verbose output:
```bash
pytest -v
```

All 16 unit tests test:
- Scene filename regex parsing and year/quality extraction
- In-memory async SQLite database CRUD operations and stats queries
- Duplicate detection by storage file ID and SHA-256 content hash
- Metadata enrichment via TMDB/OMDB and local fallback synthesis
- Telegram post text formatting and inline keyboard generation
- Local and TeraBox storage provider operations
- FastAPI `/health` and `/webhook/storage` endpoints

---

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)
```bash
# 1. Edit your .env file
nano .env

# 2. Build and launch container in detached mode
docker compose up -d --build

# 3. Check logs
docker compose logs -f

# 4. Check container health status
curl http://localhost:8080/health
```

---

## 🖥 VPS Deployment Guide (Ubuntu / Debian Systemd)

For running 24/7 on a cloud VPS (DigitalOcean, Hetzner, AWS, Linode):

### 1. Create System User and Directories
```bash
sudo useradd -r -s /bin/false botuser
sudo mkdir -p /opt/telegram-bot /var/log/telegram-bot
sudo chown -R botuser:botuser /opt/telegram-bot /var/log/telegram-bot
```

### 2. Copy Project Files & Install Dependencies
```bash
cd /opt/telegram-bot
sudo git clone <repo_url> .
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt
sudo cp .env.example .env
sudo nano .env
sudo chown -R botuser:botuser /opt/telegram-bot
```

### 3. Create Systemd Service Unit
Create `/etc/systemd/system/telegram-bot.service`:
```ini
[Unit]
Description=Production Telegram Video Automation Bot
After=network.target

[Service]
Type=simple
User=botuser
Group=botuser
WorkingDirectory=/opt/telegram-bot
EnvironmentFile=/opt/telegram-bot/.env
ExecStart=/opt/telegram-bot/venv/bin/python main.py
Restart=always
RestartSec=5
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

### 4. Start and Enable Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot

# Monitor status & live logs
sudo systemctl status telegram-bot
sudo journalctl -u telegram-bot -f
```

---

## 🤖 Telegram Bot Commands Reference

| Command | Access | Description |
| :--- | :--- | :--- |
| `/start` | Public | Welcome banner and interactive quick-start menu. |
| `/help` | Public | Complete command documentation and syntax reference. |
| `/latest` | Public | Displays the 5 most recently published media items with watch links. |
| `/search <query>` | Public | Searches database catalog by title, year, or genre. |
| `/admin` | Admin | Interactive admin dashboard with quick action buttons. |
| `/stats` | Admin | Displays detailed metrics: indexed items, published posts, failed items, storage size, and last sync timestamp. |
| `/resync` | Admin | Triggers an immediate manual storage scan and posts execution results. |
| `/add <url/filename>` | Admin | Interactive manual staging workflow (fetches metadata → renders preview → `[✅ Publish]` or `[❌ Cancel]`). |
| `/delete <message_id>` | Admin | Deletes post from channel and marks item deleted in database. |

---

## 🔒 Security & Rights Compliance

1. **Content Rights Verification**: This bot is engineered to manage authorized, user-owned, or public-domain video catalogs. It must not be used for copyright infringement.
2. **Secrets Management**: No API keys, passwords, or bot tokens are committed or hardcoded in the codebase. All credentials are read from environment variables (`.env`).
3. **Admin Guarding**: Administrative commands (`/admin`, `/stats`, `/resync`, `/add`, `/delete`) are secured by an ID-based authentication decorator matching `ADMIN_USER_IDS`.
4. **Rate Limiting**: Built-in delay throttles channel publishing (`POST_RATE_LIMIT_DELAY`) and automatically handles Telegram flood protection (`RetryAfter`).

---

## 📄 License
This project is released under the [MIT License](LICENSE).
