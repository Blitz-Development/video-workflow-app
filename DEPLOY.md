# Deployment Guide

This guide explains how to deploy the Video Workflow Web App online so others can use it.

## Quick Deploy Options

### Option 1: Render (Recommended - Easiest)

**Render** is the easiest option and supports FFmpeg out of the box.

1. **Sign up** at [render.com](https://render.com) (free tier available)

2. **Create a new Web Service**:
   - Connect your GitHub repository (or push this code to GitHub first)
   - Or use "Manual Deploy" and upload the files

3. **Configure the service**:
   - **Build Command**: `pip install -r requirements.txt && apt-get update && apt-get install -y ffmpeg`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Environment Variables**:
     - `FLASK_SECRET_KEY` = a random secret string (for sessions)
     - `OPENAI_API_KEY` = optional (users can enter their own in the web app)

4. **Deploy** - Render will build and deploy automatically

**Note**: Render's free tier spins down after inactivity. Paid plans ($7/month) keep it always on.

---

### Option 2: Railway

**Railway** is also easy and has good Python support.

1. **Sign up** at [railway.app](https://railway.app)

2. **Create a new project** and connect your GitHub repo

3. **Add environment variables**:
   - `FLASK_SECRET_KEY` = a random secret string
   - `OPENAI_API_KEY` = optional (users enter their own in the web app)

4. **Configure build**:
   - Railway auto-detects Python apps
   - Add `aptfile` with: `ffmpeg` (create `aptfile` in root)
   - Or add to `build.sh`: `apt-get update && apt-get install -y ffmpeg`

5. **Deploy** - Railway handles the rest

---

### Option 3: Fly.io

**Fly.io** supports Docker and FFmpeg easily.

1. **Install Fly CLI**: `curl -L https://fly.io/install.sh | sh`

2. **Create Dockerfile** (see below)

3. **Deploy**:
   ```bash
   fly launch
   fly secrets set FLASK_SECRET_KEY=random_string
   # OPENAI_API_KEY is optional - users enter their own in the web app
   fly deploy
   ```

---

## Docker Deployment (For Fly.io or any Docker host)

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p uploads sessions

# Expose port
EXPOSE 8080

# Run with gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "2"]
```

---

## Environment Variables Needed

Set these in your deployment platform:

- `FLASK_SECRET_KEY` - Random secret string for Flask sessions (required)
- `OPENAI_API_KEY` - Optional (users enter their own API key in the web app)
- `PORT` - Usually set automatically by the platform

**Note**: Users enter their own OpenAI API key in the web interface. This means:
- No API costs for you
- Each user uses their own quota
- More secure - keys never stored on server

---

## File Size Limits

**Important**: Most free hosting platforms have file size limits:
- **Render**: 100MB per file upload
- **Railway**: 100MB per file upload  
- **Fly.io**: Depends on plan

If users upload large videos, you may need a paid plan or use a different storage solution (S3, etc.).

---

## Security Notes

1. **Never commit** your `OPENAI_API_KEY` to GitHub
2. Use environment variables for all secrets
3. Consider adding authentication if you want to restrict access
4. The `FLASK_SECRET_KEY` should be a random string (generate with: `python -c "import secrets; print(secrets.token_hex(32))"`)

---

## Testing Locally Before Deploy

1. Install gunicorn: `pip install gunicorn`
2. Run: `gunicorn app:app --bind 0.0.0.0:5000`
3. Test at `http://localhost:5000`

---

## Which Option Should I Choose?

- **Render**: Best for beginners, easiest setup, free tier available
- **Railway**: Good balance of ease and features
- **Fly.io**: More control, good for Docker deployments
- **Self-hosted VPS**: Full control, but you manage everything

For most users, **Render** is the best starting point.

