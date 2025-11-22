# Deploy to Render - Quick Guide

## Step 1: Push to GitHub

1. **Create a new repository on GitHub** (don't initialize with README)
   - Go to: https://github.com/new
   - Name it: `video-workflow-app` (or any name you like)

2. **Push your code**:
   ```bash
   cd /Users/rensbressers/Downloads/filmpjes-jolijn
   git add .
   git commit -m "Initial commit - Video workflow web app"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/video-workflow-app.git
   git push -u origin main
   ```

   Replace `YOUR_USERNAME` with your GitHub username.

## Step 2: Deploy via Render MCP

Once your code is on GitHub, I can deploy it using Render's MCP tools. The deployment will:
- Use the GitHub repo URL
- Install FFmpeg automatically
- Set up environment variables
- Deploy the web service

## What's Been Cleaned Up

✅ **Removed obsolete files**:
- `main.py` (old CLI flow)
- `video_generator.py` (old API flow)
- `supabase_manager.py` (no longer needed)

✅ **No Supabase required** - The web app handles file uploads directly

✅ **Users enter their own API keys** - No server-side API key needed

## Files Ready for Deployment

- `app.py` - Main Flask application
- `Procfile` - Render start command
- `aptfile` - FFmpeg installation
- `requirements.txt` - Python dependencies
- `render.yaml` - Optional Render config

