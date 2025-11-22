#!/usr/bin/env python3
"""
Flask web application for manual video workflow.
Guides users through creating videos step-by-step with xAI.
"""

import logging
import os
import uuid
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from werkzeug.utils import secure_filename
import requests
from PIL import Image
import base64
import io

from config import Config
from prompt_generator import generate_clip_plan
from video_processor import extract_last_frame, strip_audio, concat_videos
from session_manager import SessionManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Generate a secret key if not provided (for production, set FLASK_SECRET_KEY env var)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32).hex()

# Security: Ensure cookies are only sent over HTTPS in production
if not os.environ.get("FLASK_DEBUG"):
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Configuration (optional - users can provide their own API key)
# If config.yaml exists, it's used for default settings, but users can override with their own key
config_file = Path(__file__).parent / "config.yaml"
config = None
try:
    if config_file.exists():
        config = Config.from_yaml(config_file)
        logger.info("Loaded config from config.yaml")
except Exception as e:
    logger.info(f"No config.yaml found or error loading it: {e}. Users will provide their own API keys.")

# Session and upload directories
UPLOAD_FOLDER = Path("uploads")
SESSIONS_DIR = Path("sessions")
UPLOAD_FOLDER.mkdir(exist_ok=True)
SESSIONS_DIR.mkdir(exist_ok=True)

ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}

session_manager = SessionManager(SESSIONS_DIR)


def allowed_file(filename: str, extensions: set) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions


def save_starting_image(file, session_id: str) -> Path:
    """Save uploaded starting image."""
    session_dir = UPLOAD_FOLDER / session_id
    session_dir.mkdir(exist_ok=True)
    
    filename = secure_filename(file.filename)
    image_path = session_dir / f"starting_image.{filename.rsplit('.', 1)[1].lower()}"
    file.save(str(image_path))
    
    # Convert to JPEG if needed
    if image_path.suffix.lower() != '.jpg':
        with Image.open(image_path) as img:
            jpeg_path = session_dir / "starting_image.jpg"
            img.convert('RGB').save(jpeg_path, 'JPEG', quality=95)
            if image_path != jpeg_path:
                image_path.unlink()
            return jpeg_path
    
    return image_path


def download_image_from_url(url: str, session_id: str) -> Path:
    """Download image from URL."""
    session_dir = UPLOAD_FOLDER / session_id
    session_dir.mkdir(exist_ok=True)
    
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    image_path = session_dir / "starting_image.jpg"
    with image_path.open("wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    
    return image_path


def image_to_data_url(image_path: Path) -> str:
    """Convert image to data URL for easy copying."""
    with open(image_path, "rb") as f:
        img_data = f.read()
        base64_data = base64.b64encode(img_data).decode('utf-8')
        ext = image_path.suffix.lower().lstrip('.')
        if ext == 'jpg':
            ext = 'jpeg'
        return f"data:image/{ext};base64,{base64_data}"


@app.route('/')
def index():
    """Initial form: scene description and starting image."""
    return render_template('index.html')


@app.route('/create', methods=['POST'])
def create():
    """Create a new session from scene description and starting image."""
    # Get OpenAI API key from user input
    openai_api_key = request.form.get('openai_api_key', '').strip()
    scene_description = request.form.get('scene_description', '').strip()
    num_clips = int(request.form.get('num_clips', 4))
    
    if not openai_api_key:
        flash('OpenAI API key is required', 'error')
        return redirect(url_for('index'))
    
    if not scene_description:
        flash('Scene description is required', 'error')
        return redirect(url_for('index'))
    
    # Handle starting image
    starting_image_path = None
    session_id = None
    
    try:
        # Generate prompts first (before creating session)
        prompts = generate_clip_plan(openai_api_key, scene_description, num_clips)
        
        # Create session first to get the session_id
        # We'll use a temporary path for now, then update it
        temp_image_path = "/tmp/temp_starting_image.jpg"
        session_id = session_manager.create_session(
            scene_description=scene_description,
            starting_image_path=temp_image_path,  # Temporary, will update
            prompts=prompts,
            num_clips=num_clips,
            openai_api_key=openai_api_key
        )
        
        # Now handle image upload or URL with the correct session_id
        session_dir = UPLOAD_FOLDER / session_id
        session_dir.mkdir(exist_ok=True)
        
        starting_image_path = None
        
        # Handle image upload or URL
        if 'starting_image_file' in request.files:
            file = request.files['starting_image_file']
            if file and file.filename and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                starting_image_path = save_starting_image(file, session_id)
        elif request.form.get('starting_image_url'):
            image_url = request.form.get('starting_image_url', '').strip()
            if image_url:
                starting_image_path = download_image_from_url(image_url, session_id)
        
        if not starting_image_path or not starting_image_path.exists():
            flash('Starting image is required (upload file or provide URL)', 'error')
            # Clean up session
            session_file = SESSIONS_DIR / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
            return redirect(url_for('index'))
        
        # Update session with correct image path
        session_manager.update_session(session_id, starting_image_path=str(starting_image_path))
        
        return redirect(url_for('plan', session_id=session_id))
        
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        flash(f'Error creating session: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.route('/plan/<session_id>')
def plan(session_id: str):
    """Display all prompts and starting image."""
    session = session_manager.get_session(session_id)
    if not session:
        flash('Session not found', 'error')
        return redirect(url_for('index'))
    
    starting_image_path = Path(session.starting_image_path)
    image_data_url = image_to_data_url(starting_image_path) if starting_image_path.exists() else None
    
    return render_template('plan.html', 
                         session=session,
                         starting_image_path=starting_image_path,
                         image_data_url=image_data_url)


@app.route('/step/<session_id>/<int:step_num>')
def step(session_id: str, step_num: int):
    """Show current step with image and prompt to copy."""
    session = session_manager.get_session(session_id)
    if not session:
        flash('Session not found', 'error')
        return redirect(url_for('index'))
    
    if step_num < 1 or step_num > len(session.prompts):
        flash('Invalid step number', 'error')
        return redirect(url_for('plan', session_id=session_id))
    
    # Get image for this step
    if step_num == 1:
        image_path = Path(session.starting_image_path)
    else:
        # Use last frame from previous step
        if len(session.last_frames) >= step_num - 1:
            image_path = Path(session.last_frames[step_num - 2])
        else:
            flash('Previous step not completed', 'error')
            return redirect(url_for('plan', session_id=session_id))
    
    if not image_path.exists():
        flash('Image not found', 'error')
        return redirect(url_for('plan', session_id=session_id))
    
    prompt = session.prompts[step_num - 1]
    image_data_url = image_to_data_url(image_path)
    
    is_complete = len(session.uploaded_videos) >= step_num
    
    return render_template('step.html',
                         session=session,
                         step_num=step_num,
                         prompt=prompt,
                         image_path=image_path,
                         image_data_url=image_data_url,
                         is_complete=is_complete)


@app.route('/upload/<session_id>/<int:step_num>', methods=['POST'])
def upload(session_id: str, step_num: int):
    """Handle video upload for a step."""
    session = session_manager.get_session(session_id)
    if not session:
        flash('Session not found', 'error')
        return redirect(url_for('index'))
    
    if 'video' not in request.files:
        flash('No video file provided', 'error')
        return redirect(url_for('step', session_id=session_id, step_num=step_num))
    
    file = request.files['video']
    if not file or not file.filename:
        flash('No video file selected', 'error')
        return redirect(url_for('step', session_id=session_id, step_num=step_num))
    
    if not allowed_file(file.filename, ALLOWED_VIDEO_EXTENSIONS):
        flash('Invalid file type. Please upload MP4, MOV, or AVI.', 'error')
        return redirect(url_for('step', session_id=session_id, step_num=step_num))
    
    try:
        session_dir = UPLOAD_FOLDER / session_id
        session_dir.mkdir(exist_ok=True)
        
        # Save uploaded video
        video_filename = f"step_{step_num}.mp4"
        video_path = session_dir / video_filename
        file.save(str(video_path))
        
        # Strip audio
        silent_video_path = session_dir / f"step_{step_num}_silent.mp4"
        strip_audio(video_path, silent_video_path)
        
        # Extract last frame
        frame_path = session_dir / f"step_{step_num}_frame.jpg"
        extract_last_frame(silent_video_path, frame_path)
        
        # Update session
        session_manager.add_uploaded_video(
            session_id,
            str(silent_video_path),
            str(frame_path)
        )
        
        # Move to next step or show combine page
        if step_num < len(session.prompts):
            return redirect(url_for('step', session_id=session_id, step_num=step_num + 1))
        else:
            return redirect(url_for('combine', session_id=session_id))
            
    except Exception as e:
        logger.error(f"Error uploading video: {e}")
        flash(f'Error processing video: {str(e)}', 'error')
        return redirect(url_for('step', session_id=session_id, step_num=step_num))


@app.route('/combine/<session_id>')
def combine(session_id: str):
    """Final step: combine all videos."""
    session = session_manager.get_session(session_id)
    if not session:
        flash('Session not found', 'error')
        return redirect(url_for('index'))
    
    if not session_manager.is_complete(session_id):
        flash('Not all videos have been uploaded', 'error')
        return redirect(url_for('plan', session_id=session_id))
    
    # Check if already combined
    session_dir = UPLOAD_FOLDER / session_id
    final_output = session_dir / "final_output.mp4"
    
    return render_template('combine.html',
                         session=session,
                         final_output=final_output,
                         is_combined=final_output.exists())


@app.route('/combine/<session_id>/generate', methods=['POST'])
def generate_final(session_id: str):
    """Generate final combined video."""
    session = session_manager.get_session(session_id)
    if not session:
        flash('Session not found', 'error')
        return redirect(url_for('index'))
    
    if not session_manager.is_complete(session_id):
        flash('Not all videos have been uploaded', 'error')
        return redirect(url_for('plan', session_id=session_id))
    
    try:
        session_dir = UPLOAD_FOLDER / session_id
        video_files = [Path(video_path) for video_path in session.uploaded_videos]
        
        # Verify all files exist
        for video_path in video_files:
            if not video_path.exists():
                flash(f'Video file not found: {video_path}', 'error')
                return redirect(url_for('combine', session_id=session_id))
        
        final_output = session_dir / "final_output.mp4"
        
        # Convert to absolute paths for concat_videos
        video_files_abs = [vf.resolve() for vf in video_files]
        concat_videos(video_files_abs, final_output.resolve())
        
        flash('Video combination complete!', 'success')
        return redirect(url_for('combine', session_id=session_id))
        
    except Exception as e:
        logger.error(f"Error combining videos: {e}")
        flash(f'Error combining videos: {str(e)}', 'error')
        return redirect(url_for('combine', session_id=session_id))


@app.route('/download/<session_id>')
def download(session_id: str):
    """Download the final combined video."""
    session = session_manager.get_session(session_id)
    if not session:
        flash('Session not found', 'error')
        return redirect(url_for('index'))
    
    session_dir = UPLOAD_FOLDER / session_id
    final_output = session_dir / "final_output.mp4"
    
    if not final_output.exists():
        flash('Final video not found. Please generate it first.', 'error')
        return redirect(url_for('combine', session_id=session_id))
    
    return send_file(str(final_output), as_attachment=True, download_name='final_output.mp4')


@app.route('/image/<session_id>/<int:step_num>')
def get_image(session_id: str, step_num: int):
    """Serve image file for download."""
    session = session_manager.get_session(session_id)
    if not session:
        return "Session not found", 404
    
    if step_num == 1:
        image_path = Path(session.starting_image_path)
    else:
        if len(session.last_frames) >= step_num - 1:
            image_path = Path(session.last_frames[step_num - 2])
        else:
            return "Image not found", 404
    
    if not image_path.exists():
        return "Image not found", 404
    
    return send_file(str(image_path), mimetype='image/jpeg')


if __name__ == '__main__':
    # For production, use gunicorn instead
    # For local development:
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

