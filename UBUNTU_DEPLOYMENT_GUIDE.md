# Ubuntu Deployment Guide - Step by Step

This guide will help you deploy your Nexus bot on an Ubuntu server, complete with setup, deployment, refresh/restart procedures, and rollback capabilities.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Server Setup](#initial-server-setup)
3. [Install Required Dependencies](#install-required-dependencies)
4. [Clone and Configure the Project](#clone-and-configure-the-project)
5. [Set Up Environment Variables](#set-up-environment-variables)
6. [Set Up PostgreSQL Database](#set-up-postgresql-database)
7. [Set Up Redis](#set-up-redis)
8. [Run Database Migrations](#run-database-migrations)
9. [Start the Bot](#start-the-bot)
10. [Set Up Systemd Service (Auto-start)](#set-up-systemd-service-auto-start)
11. [Deploying Code Changes](#deploying-code-changes)
12. [Going Back/Rollback](#going-backrollback)
13. [Monitoring and Logs](#monitoring-and-logs)
14. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Ubuntu 20.04, 22.04, or 24.04
- Root or sudo access
- At least 2GB RAM (4GB recommended)
- 20GB free disk space
- Basic knowledge of command line

---

## Initial Server Setup

### 1. Update Your System

```bash
# Update package list and upgrade existing packages
sudo apt update && sudo apt upgrade -y
```

### 2. Create a Dedicated User (Recommended)

```bash
# Create a user for running the bot
sudo adduser nexus

# Add user to sudo group (if needed)
sudo usermod -aG sudo nexus

# Switch to the new user
su - nexus
```

### 3. Set Up Firewall

```bash
# Enable UFW (Uncomplicated Firewall)
sudo ufw allow OpenSSH
sudo ufw allow 8000/tcp  # If you want to expose the API
sudo ufw allow 6379/tcp  # If you need external Redis access
sudo ufw enable
```

---

## Install Required Dependencies

### 1. Install Python and System Tools

```bash
# Install Python 3.10+ and pip
sudo apt install -y python3 python3-pip python3-venv git curl wget

# Verify Python version
python3 --version
# Should be 3.10 or higher
```

### 2. Install FFmpeg (Required for Music)

```bash
# Add repository and install FFmpeg
sudo apt install -y ffmpeg

# Verify FFmpeg installation
ffmpeg -version
```

### 3. Install Node.js (Required for Mini App)

```bash
# Install Node.js 18+ using NodeSource
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Verify Node.js version
node --version
npm --version
```

---

## Clone and Configure the Project

### 1. Clone the Repository

```bash
# Navigate to home directory
cd ~

# Clone your repository (replace with your actual repo URL)
git clone https://github.com/yourusername/your-repo.git nexus-bot

# Enter the project directory
cd nexus-bot
```

### 2. Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# You should see (venv) in your prompt now
```

### 3. Install Python Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt
```

### 4. Install Mini App Dependencies

```bash
# Navigate to miniapp directory
cd miniapp

# Install Node.js dependencies
npm install

# Go back to project root
cd ..
```

---

## Set Up Environment Variables

### 1. Create Environment File

```bash
# Copy example environment file
cp .env.example .env

# Edit the environment file
nano .env
```

### 2. Fill in Required Variables

In `.env`, you MUST set these values:

```bash
# ── REQUIRED ─────────────────────────────
PRIMARY_BOT_TOKEN=your_bot_token_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_key_here
SUPABASE_CONNECTION_STRING=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres
SECRET_KEY=your_fernet_key_here  # Generate with command below
OWNER_ID=123456789  # Your Telegram user ID

# ── BOT DISPLAY ───────────────────────────
BOT_DISPLAY_NAME=Nexus
MAIN_BOT_USERNAME=YourBotUsername

# ── MUSIC SETTINGS ────────────────────────
PYROGRAM_API_ID=12345678  # Get from https://my.telegram.org/apps
PYROGRAM_API_HASH=your_api_hash_here

# ── REDIS ─────────────────────────────────
REDIS_URL=redis://localhost:6379
```

### 3. Generate SECRET_KEY

```bash
# Generate a Fernet key for encryption
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output and paste it as `SECRET_KEY` in your `.env` file.

### 4. Get Your Telegram User ID

```bash
# You can get your user ID from Telegram by:
# 1. Message @userinfobot on Telegram
# 2. It will reply with your user ID
```

### 5. Get Telegram Bot Token

1. Message @BotFather on Telegram
2. Send `/newbot`
3. Follow the prompts to create a bot
4. Copy the token (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 6. Get Pyrogram API Credentials

1. Go to https://my.telegram.org/apps
2. Log in with your phone number
3. Click "Create new application"
4. Fill in the form (any values work)
5. Copy `api_id` and `api_hash`

---

## Set Up PostgreSQL Database

### Option A: Use Supabase (Recommended)

1. Go to https://supabase.com
2. Create a free account
3. Create a new project
4. Go to Settings → Database
5. Copy connection string from "Connection string" section
6. Paste in `.env` as `SUPABASE_CONNECTION_STRING`

### Option B: Install Local PostgreSQL

```bash
# Install PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Switch to postgres user
sudo -i -u postgres

# Create database and user
psql
```

In the PostgreSQL prompt:

```sql
CREATE DATABASE nexus_bot;
CREATE USER nexus_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE nexus_bot TO nexus_user;
\q
```

Update your `.env` file:

```bash
SUPABASE_CONNECTION_STRING=postgresql://nexus_user:your_secure_password@localhost:5432/nexus_bot
```

---

## Set Up Redis

### Install and Start Redis

```bash
# Install Redis
sudo apt install -y redis-server

# Start Redis service
sudo systemctl start redis
sudo systemctl enable redis

# Verify Redis is running
redis-cli ping
# Should return: PONG

# Test connection
redis-cli
# In Redis CLI: ping
# Exit with: exit
```

---

## Run Database Migrations

```bash
# Ensure virtual environment is active
source ~/nexus-bot/venv/bin/activate
cd ~/nexus-bot

# Run migrations (if you have migration scripts)
# Check the db/migrations directory for SQL files
python -c "
import asyncio
import asyncpg
from config import settings

async def run_migrations():
    conn = await asyncpg.connect(settings.SUPABASE_CONNECTION_STRING)
    
    # Read and execute migration files
    import os
    for filename in sorted(os.listdir('db/migrations')):
        if filename.endswith('.sql'):
            with open(f'db/migrations/{filename}') as f:
                sql = f.read()
                await conn.execute(sql)
                print(f'✓ Executed {filename}')
    
    await conn.close()
    print('All migrations completed!')

asyncio.run(run_migrations())
"
```

---

## Start the Bot

### Manual Start (For Testing)

```bash
# Activate virtual environment
source ~/nexus-bot/venv/bin/activate
cd ~/nexus-bot

# Start the bot
python main.py
```

Press `Ctrl+C` to stop the bot.

---

## Set Up Systemd Service (Auto-Start)

### 1. Create Systemd Service File

```bash
# Create service file
sudo nano /etc/systemd/system/nexus-bot.service
```

Paste the following:

```ini
[Unit]
Description=Nexus Telegram Bot
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=nexus
WorkingDirectory=/home/nexus/nexus-bot
Environment="PATH=/home/nexus/nexus-bot/venv/bin"
ExecStart=/home/nexus/nexus-bot/venv/bin/python main.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 2. Enable and Start the Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable nexus-bot

# Start the service
sudo systemctl start nexus-bot

# Check status
sudo systemctl status nexus-bot
```

### 3. View Logs

```bash
# View real-time logs
sudo journalctl -u nexus-bot -f

# View last 100 lines
sudo journalctl -u nexus-bot -n 100

# View logs since today
sudo journalctl -u nexus-bot --since today
```

---

## Deploying Code Changes

### Method 1: Manual Pull and Restart

```bash
# SSH into your server
ssh nexus@your-server-ip

# Navigate to project directory
cd ~/nexus-bot

# Pull latest changes from git
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Update dependencies if requirements.txt changed
pip install -r requirements.txt --upgrade

# Update miniapp dependencies if package.json changed
cd miniapp
npm install
cd ..

# Restart the bot service
sudo systemctl restart nexus-bot

# Check status
sudo systemctl status nexus-bot
```

### Method 2: Using a Deploy Script (Recommended)

Create a deploy script:

```bash
nano ~/deploy.sh
```

Paste:

```bash
#!/bin/bash

# Nexus Bot Deploy Script
# Usage: ./deploy.sh

echo "🚀 Starting deployment..."

# Navigate to project
cd ~/nexus-bot

# Pull latest changes
echo "📥 Pulling latest code..."
git pull origin main

# Check if pull was successful
if [ $? -ne 0 ]; then
    echo "❌ Git pull failed. Aborting."
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Update Python dependencies
echo "📦 Updating Python dependencies..."
pip install -r requirements.txt --upgrade

# Update Node.js dependencies
echo "📦 Updating Node.js dependencies..."
cd miniapp
npm install
cd ..

# Restart service
echo "🔄 Restarting bot service..."
sudo systemctl restart nexus-bot

# Wait for service to start
sleep 5

# Check status
if sudo systemctl is-active --quiet nexus-bot; then
    echo "✅ Deployment successful! Bot is running."
    sudo systemctl status nexus-bot --no-pager
else
    echo "❌ Deployment failed! Check logs with: journalctl -u nexus-bot -f"
    exit 1
fi
```

Make it executable:

```bash
chmod +x ~/deploy.sh
```

Now you can deploy with:

```bash
./deploy.sh
```

---

## Going Back/Rollback

### Method 1: Git Reset to Previous Commit

```bash
# View recent commits
git log --oneline -10

# Reset to previous commit (replace abc123 with commit hash)
git reset --hard abc123

# Restart the bot
sudo systemctl restart nexus-bot
```

### Method 2: Git Revert (Safer)

```bash
# Revert last commit (keeps history)
git revert HEAD

# Push the revert
git push origin main

# Restart service
sudo systemctl restart nexus-bot
```

### Method 3: Using a Rollback Script

Create a rollback script:

```bash
nano ~/rollback.sh
```

Paste:

```bash
#!/bin/bash

# Nexus Bot Rollback Script
# Usage: ./rollback.sh [commit_hash]

if [ -z "$1" ]; then
    echo "Usage: ./rollback.sh <commit_hash>"
    echo ""
    echo "Available commits:"
    git log --oneline -10
    exit 1
fi

COMMIT_HASH=$1

echo "⏪ Rolling back to commit: $COMMIT_HASH"

# Navigate to project
cd ~/nexus-bot

# Create backup of current state
BACKUP_DIR="/tmp/nexus-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r . "$BACKUP_DIR"
echo "📦 Backup created at: $BACKUP_DIR"

# Reset to specified commit
git reset --hard $COMMIT_HASH

# Activate virtual environment
source venv/bin/activate

# Restore dependencies
pip install -r requirements.txt --upgrade
cd miniapp
npm install
cd ..

# Restart service
echo "🔄 Restarting bot service..."
sudo systemctl restart nexus-bot

# Wait for service to start
sleep 5

# Check status
if sudo systemctl is-active --quiet nexus-bot; then
    echo "✅ Rollback successful! Bot is running."
    sudo systemctl status nexus-bot --no-pager
else
    echo "❌ Rollback failed! Restoring from backup..."
    cp -r "$BACKUP_DIR"/* .
    sudo systemctl restart nexus-bot
    echo "Backup restored. Please check logs manually."
fi
```

Make it executable:

```bash
chmod +x ~/rollback.sh
```

Usage:

```bash
# View commits
git log --oneline -10

# Rollback to specific commit
./rollback.sh abc123def456
```

---

## Monitoring and Logs

### Check Bot Status

```bash
# Check if bot is running
sudo systemctl status nexus-bot

# Check bot logs (real-time)
sudo journalctl -u nexus-bot -f

# Check last 50 lines
sudo journalctl -u nexus-bot -n 50

# Check logs from last hour
sudo journalctl -u nexus-bot --since "1 hour ago"

# Check for errors only
sudo journalctl -u nexus-bot -p err
```

### Check Services

```bash
# Check all services status
sudo systemctl status postgresql
sudo systemctl status redis
sudo systemctl status nexus-bot
```

### Monitor Resources

```bash
# Check CPU and memory usage
htop
# Install with: sudo apt install htop

# Check disk usage
df -h

# Check memory usage
free -h

# Check bot process
ps aux | grep python
```

---

## Troubleshooting

### Bot Won't Start

```bash
# Check service status
sudo systemctl status nexus-bot

# Check recent logs
sudo journalctl -u nexus-bot -n 50

# Check if port is in use
sudo netstat -tlnp | grep 8000

# Test Python dependencies
source venv/bin/activate
python -c "import telegram; print('✓ python-telegram-bot OK')"
python -c "import asyncpg; print('✓ asyncpg OK')"
python -c "import redis; print('✓ redis OK')"
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql -h localhost -U nexus_user -d nexus_bot

# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection string in .env
cat .env | grep SUPABASE_CONNECTION_STRING
```

### Redis Connection Issues

```bash
# Test Redis connection
redis-cli ping

# Check Redis is running
sudo systemctl status redis

# Test from Python
source venv/bin/activate
python -c "import redis; r = redis.from_url('redis://localhost:6379'); print(r.ping())"
```

### Music/FFmpeg Issues

```bash
# Check FFmpeg is installed
ffmpeg -version

# Test audio download
source venv/bin/activate
python -c "import yt_dlp; print('✓ yt-dlp OK')"
```

### Permission Issues

```bash
# Fix file permissions
sudo chown -R nexus:nexus ~/nexus-bot
chmod +x ~/deploy.sh
chmod +x ~/rollback.sh
```

---

## Useful Commands Summary

```bash
# Deploy updates
cd ~/nexus-bot && ./deploy.sh

# Rollback to previous version
cd ~/nexus-bot && git log --oneline -10
cd ~/nexus-bot && ./rollback.sh <commit_hash>

# View logs
sudo journalctl -u nexus-bot -f

# Restart bot
sudo systemctl restart nexus-bot

# Stop bot
sudo systemctl stop nexus-bot

# Start bot
sudo systemctl start nexus-bot

# Check status
sudo systemctl status nexus-bot

# SSH into server
ssh nexus@your-server-ip

# Check Python environment
source ~/nexus-bot/venv/bin/activate
which python
python --version
pip list
```

---

## Additional Tips

### 1. Set Up Automated Backups

```bash
# Create backup script
nano ~/backup.sh
```

```bash
#!/bin/bash
# Backup database and configuration

BACKUP_DIR="/home/nexus/backups"
DATE=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BACKUP_DIR"

# Backup database
pg_dump $SUPABASE_CONNECTION_STRING > "$BACKUP_DIR/db-$DATE.sql"

# Backup environment file
cp .env "$BACKUP_DIR/.env-$DATE"

# Delete backups older than 7 days
find "$BACKUP_DIR" -name "*.sql" -mtime +7 -delete
find "$BACKUP_DIR" -name ".env-*" -mtime +7 -delete

echo "✓ Backup completed: $DATE"
```

```bash
chmod +x ~/backup.sh

# Add to crontab for daily backups
crontab -e
# Add this line (runs daily at 3 AM):
# 0 3 * * * /home/nexus/backup.sh >> /home/nexus/backup.log 2>&1
```

### 2. Set Up Monitoring (Optional)

Install monitoring tools:

```bash
# Install Node Exporter for Prometheus
wget https://github.com/prometheus/node_exporter/releases/download/v1.6.1/node_exporter-1.6.1.linux-amd64.tar.gz
tar xvfz node_exporter-1.6.1.linux-amd64.tar.gz
sudo mv node_exporter-1.6.1.linux-amd64/node_exporter /usr/local/bin/
sudo useradd --no-create-home --shell /bin/false node_exporter
sudo chown node_exporter:node_exporter /usr/local/bin/node_exporter

# Create systemd service
sudo nano /etc/systemd/system/node_exporter.service
```

```ini
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable node_exporter
sudo systemctl start node_exporter
```

---

## Quick Reference Card

Print this for quick access:

```bash
# DEPLOY
./deploy.sh

# ROLLBACK
git log --oneline -10
./rollback.sh <hash>

# LOGS
sudo journalctl -u nexus-bot -f

# RESTART
sudo systemctl restart nexus-bot

# STATUS
sudo systemctl status nexus-bot

# STOP
sudo systemctl stop nexus-bot

# START
sudo systemctl start nexus-bot

# CHECK ALL SERVICES
sudo systemctl status postgresql redis nexus-bot
```

---

## Need Help?

If you encounter any issues:

1. Check the logs: `sudo journalctl -u nexus-bot -n 100`
2. Verify all services are running
3. Check environment variables in `.env`
4. Ensure all dependencies are installed

---

**That's it! You now have a complete Ubuntu deployment setup with easy deploy, rollback, and monitoring capabilities! 🎉**
