# AI Video Story Generator

Generate multi-clip AI videos using:
- XAI Grok for intelligent scene planning
- Kie.ai (or compatible API) for video generation  
- Supabase for frame storage and chaining
- FFmpeg for processing and concatenation

## Architecture

```
main.py                  # Orchestration
├── config.py           # Configuration loading
├── prompt_generator.py # XAI Grok prompts
├── supabase_manager.py # Image uploads
├── video_generator.py  # Video API calls
└── video_processor.py  # FFmpeg operations
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

ffmpeg should already be available on your Mac. If not:
```bash
brew install ffmpeg
```

### 2. Configure API Details

Edit `config.yaml`:
- Set your actual video API base URL and endpoint URLs
- Update `starting_image_url` with a publicly accessible image
- Customize scene description, num_clips, quality, duration, etc.
- Set `planning.use_xai: true/false` to enable/disable Grok planning

### 3. Set API Keys

**Video API Key (required):**
```bash
export VIDEO_API_KEY="your_actual_api_key_here"
```

**XAI API Key (required if using Grok planning):**
```bash
export XAI_API_KEY="your_xai_api_key_here"
```

Get your XAI API key from: https://console.x.ai/

**Supabase Credentials (required if frame chaining is enabled):**
```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your_service_role_key_here"
```

**Important**: Use the **service_role** key (not the anon key) for storage uploads. The service_role key bypasses Row Level Security (RLS) policies, which is required for programmatic storage uploads. You can find your service_role key in your Supabase project settings under API → service_role (keep this secret!).

## Running

```bash
chmod +x main.py
./main.py
```

The script will:
1. Load config from `config.yaml`
2. Upload starting image to Supabase
3. Generate intelligent prompts using XAI Grok
4. For each prompt:
   - Generate video using image + prompt
   - Download video
   - Strip audio
   - Extract last frame → upload to Supabase → use as next clip's image
5. Concatenate all clips into `generated_clips/final_output.mp4`

## File Structure

| File | Purpose |
|------|---------|
| `main.py` | Entry point - orchestrates the flow |
| `config.py` | Configuration management with validation |
| `prompt_generator.py` | XAI Grok integration for scene planning |
| `supabase_manager.py` | Supabase Storage uploads |
| `video_generator.py` | Video API calls (Kie.ai or compatible) |
| `video_processor.py` | FFmpeg operations (audio strip, frame extraction, concatenation) |
| `config.yaml` | Configuration file (API endpoints, prompts, settings) |

## How It Works

1. **Config Loading** (`config.py`)
   - Validates environment variables
   - Loads YAML configuration

2. **Image Upload** (main.py → `supabase_manager.py`)
   - Uploads initial image to Supabase
   - Gets public URL for video API

3. **Prompt Planning** (`prompt_generator.py`)
   - Sends scene to XAI Grok
   - Grok creates sequential prompts
   - Falls back to simple splitting if Grok fails

4. **Video Generation Loop** (main.py → `video_generator.py` → `video_processor.py`)
   - For each prompt:
     - Call video API with (image URL + prompt)
     - Download generated video
     - Strip audio with FFmpeg
     - Extract last frame
     - Upload frame to Supabase
     - Use new frame URL for next iteration

5. **Final Concatenation** (`video_processor.py`)
   - Combine all silent clips
   - Output: `generated_clips/final_output.mp4`

## What You Still Need to Configure

### API Endpoints

Check your video API documentation for the exact endpoints:

- **Generate endpoint**: Usually `/api/v1/video/generate`
- **Status endpoint**: Might be `/api/v1/video/status/{task_id}`, `/api/v1/video/task/{task_id}`, etc.

Update these in `config.yaml`.

### Status Response Structure

Your API might return status differently. In `poll_video_status()`, adjust:
```python
status = data.get("data", {}).get("status")
```

And in `main()`, adjust video URL extraction:
```python
video_url = status_data.get("data", {}).get("videoUrl")
```

### Frame Reuse (Advanced)

To automatically use the last frame of one clip as input for the next clip:

1. Choose a storage service (S3, Supabase, Google Cloud Storage, etc.)
2. Create an `upload_frame_and_get_url(path: Path) -> str` function
3. Uncomment the line in the main loop:
   ```python
   current_image_url = upload_frame_and_get_url(last_frame_path)
   ```

## Troubleshooting

- **"VIDEO_API_KEY is not set"**: Run `export VIDEO_API_KEY="your_key"`
- **"XAI_API_KEY is not set"**: Run `export XAI_API_KEY="your_key"` (only needed if using Grok planning)
- **"ffmpeg command failed"**: Check ffmpeg is installed (`ffmpeg -version`)
- **XAI Grok planning failed**: Check your XAI API key and that you have API credits
  - If it fails, the script falls back to simple splitting automatically
- **"row-level security policy" or "403 Unauthorized" errors**: 
  - You're likely using the anon key instead of the service_role key
  - Run `export SUPABASE_SERVICE_ROLE_KEY="your_service_role_key"` instead of `SUPABASE_KEY`
  - The service_role key is required for storage uploads when RLS is enabled
- **API errors**: Review logs and check your config.yaml matches your API's actual structure
- **Large download times**: Normal for high-quality videos; be patient or adjust poll interval

## Logs

All operations log to console with timestamps:
- `INFO`: Major operations (clip generation, downloads, concatenation)
- `DEBUG`: Detailed ffmpeg and API calls
- `WARNING`: Fallbacks (e.g., XAI planning failed, using simple splitting)
- `ERROR`: Failures that stop execution

Check logs for debugging API issues or prompt inspection.

