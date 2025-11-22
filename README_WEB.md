# Video Workflow Web App

A Flask web application that guides you through creating multi-clip videos manually using xAI. Instead of automatically generating videos via API, the app breaks your scene into prompts and guides you step-by-step.

## Features

- **Scene Planning**: Enter a scene description and starting image. AI breaks it into sequential prompts.
- **Step-by-Step Guide**: For each step, you get:
  - A starting image to copy/download
  - A prompt to copy
  - Instructions to create the video in xAI
  - Upload form for your created video
- **Automatic Frame Extraction**: After each upload, the app extracts the last frame for the next step.
- **Video Combination**: When all videos are uploaded, combine them into a single silent video.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install FFmpeg

FFmpeg is required for video processing. On macOS:

```bash
brew install ffmpeg
```

### 3. Set Environment Variables

```bash
export OPENAI_API_KEY="your_openai_api_key_here"
```

(You can also use `VIDEO_API_KEY` for backward compatibility)

### 4. Run the Application

```bash
python app.py
```

The app will be available at `http://127.0.0.1:5000`

## Usage

1. **Start**: Enter your scene description, number of clips, and upload/enter URL for starting image.
2. **Plan**: Review the generated prompts and starting image.
3. **For Each Step**:
   - Copy the starting image (or download it)
   - Copy the prompt
   - Go to xAI and create a video using the image and prompt
   - Download the video from xAI
   - Upload it to the app
4. **Combine**: When all videos are uploaded, click "Combine All Videos" to create the final output.

## File Structure

- `app.py` - Main Flask application
- `session_manager.py` - Session state management
- `prompt_generator.py` - AI prompt generation (reused from original)
- `video_processor.py` - Video processing functions (reused from original)
- `templates/` - HTML templates
- `static/` - CSS styles
- `uploads/` - User-uploaded videos and generated files (created automatically)
- `sessions/` - Session state files (created automatically)

## Configuration

The app uses a simplified `config.yaml`. Only the output directory is needed from the config file. The OpenAI API key is read from the `OPENAI_API_KEY` environment variable.

