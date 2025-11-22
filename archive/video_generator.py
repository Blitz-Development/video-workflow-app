import logging
import time
from pathlib import Path
from typing import Optional
import requests
from PIL import Image
from config import Config

logger = logging.getLogger(__name__)


def resize_image_to_video_size(image_path: Path, video_size: str) -> None:
    """
    Resize image to match the requested video dimensions.
    
    Args:
        image_path: Path to the image file (will be modified in place)
        video_size: Video size string in format "WIDTHxHEIGHT" (e.g., "1280x720")
    """
    width, height = map(int, video_size.split("x"))
    
    with Image.open(image_path) as img:
        current_size = img.size
        
        # Only resize if dimensions don't match
        if current_size != (width, height):
            logger.info(f"Resizing image from {current_size[0]}x{current_size[1]} to {width}x{height}")
            # Use LANCZOS resampling for high quality
            resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
            resized_img.save(image_path, "JPEG", quality=95)
            logger.debug(f"Image resized successfully")
        else:
            logger.debug(f"Image already matches video size {width}x{height}")


def download_image_to_temp(image_url: str, temp_path: Path, config: Optional[Config] = None) -> None:
    """
    Download image from URL to temporary file for Sora upload.
    
    If the URL is from Supabase Storage and config is provided, uses authenticated download.
    Otherwise, uses direct HTTP GET.
    After downloading, resizes the image to match the requested video dimensions.
    """
    logger.debug(f"Downloading image for Sora: {image_url}")
    
    # Check if this is a Supabase Storage URL and we have config
    if config and "supabase.co/storage" in image_url:
        # Extract filename from URL
        # URL format: https://project.supabase.co/storage/v1/object/public/bucket/filename
        # or: https://project.supabase.co/storage/v1/object/public/bucket/path/to/file.jpg
        try:
            from supabase_manager import download_image_from_supabase
            
            # Extract bucket and filename from URL
            # Split URL to get the path after /public/
            parts = image_url.split("/storage/v1/object/public/")
            if len(parts) == 2:
                bucket_and_path = parts[1]
                # Split bucket and filename
                bucket_path_parts = bucket_and_path.split("/", 1)
                if len(bucket_path_parts) == 2:
                    bucket = bucket_path_parts[0]
                    filename = bucket_path_parts[1]
                    
                    # Verify bucket matches config
                    if bucket == config.supabase_bucket:
                        logger.debug(f"Using authenticated Supabase download for: {filename}")
                        download_image_from_supabase(config, filename, temp_path)
                        # Resize to match video dimensions
                        if config:
                            resize_image_to_video_size(temp_path, config.video_size)
                        return
            
            # If we can't parse the URL, fall through to HTTP download
            logger.warning(f"Could not parse Supabase URL, falling back to HTTP: {image_url}")
        except Exception as e:
            logger.warning(f"Failed to use Supabase authenticated download, falling back to HTTP: {e}")
    
    # Fallback to direct HTTP download
    response = requests.get(image_url, stream=True)
    response.raise_for_status()
    
    with temp_path.open("wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    
    # Resize to match video dimensions after download
    if config:
        resize_image_to_video_size(temp_path, config.video_size)


def call_generate_video_api(
    config: Config,
    prompt: str,
    image_url: Optional[str],
) -> str:
    """
    Call OpenAI Sora API for video generation.
    
    Sora requires:
    - Image file upload (multipart/form-data)
    - Prompt text
    - Model, size, duration
    """
    if not image_url:
        raise RuntimeError("Image URL is required for video generation")
    
    headers = {
        "Authorization": f"Bearer {config.api_key}",
    }

    logger.info(f"Requesting video generation: {prompt!r}")
    
    # Download image to temp file for multipart upload
    temp_image = Path("/tmp/sora_image.jpg")
    try:
        download_image_to_temp(image_url, temp_image, config)
        
        # Prepare multipart form data
        files = {
            "input_reference": ("image.jpg", temp_image.open("rb"), "image/jpeg"),
        }
        data = {
            "prompt": prompt,
            "model": config.sora_model,
            "size": config.video_size,
            "seconds": config.clip_duration,
        }
        
        response = requests.post(
            config.generate_endpoint,
            headers=headers,
            files=files,
            data=data,
            timeout=60,
        )
        
        if not response.ok:
            raise RuntimeError(f"Sora request failed: {response.status_code} {response.text}")

        result = response.json()
        
        # Sora returns video ID, not URL yet (need to poll)
        video_id = result.get("id")
        if not video_id:
            raise RuntimeError(f"No video ID in Sora response: {result}")
        
        logger.info(f"Video generation started, ID: {video_id}")
        return video_id
        
    finally:
        if temp_image.exists():
            temp_image.unlink()


def poll_video_status(config: Config, video_id: str) -> dict:
    """
    Poll OpenAI Sora API until video generation completes.
    
    Args:
        config: Configuration
        video_id: Video ID returned from POST /videos
    
    Returns:
        Response data from status endpoint
    """
    poll_url = f"https://api.openai.com/v1/videos/{video_id}"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
    }

    max_polls = 120  # Max 10 minutes (120 polls * 5 seconds)
    poll_count = 0
    
    while poll_count < max_polls:
        logger.info(f"Polling Sora video status (attempt {poll_count + 1}/{max_polls}): {video_id}")
        
        response = requests.get(poll_url, headers=headers)
        
        if not response.ok:
            raise RuntimeError(f"Status request failed: {response.status_code} {response.text}")

        data = response.json()
        status = data.get("status")

        logger.info(f"Video status: {status}")
        
        if status == "completed":
            logger.info("Video generation completed!")
            return data
        elif status == "failed":
            raise RuntimeError(f"Video generation failed: {data}")
        elif status in ("pending", "processing"):
            time.sleep(config.poll_interval_seconds)
            poll_count += 1
        else:
            logger.warning(f"Unknown status: {status}")
            time.sleep(config.poll_interval_seconds)
            poll_count += 1
    
    raise RuntimeError(f"Video generation timeout after {max_polls * config.poll_interval_seconds} seconds")


def download_video_from_sora(config: Config, video_id: str, output_path: Path) -> None:
    """
    Download the generated video file from Sora API using the download endpoint.
    
    Args:
        config: Configuration
        video_id: Video ID from completed video
        output_path: Path to save the downloaded video
    """
    download_url = f"https://api.openai.com/v1/videos/{video_id}/download"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
    }
    
    logger.info(f"Downloading video from Sora: {video_id}")
    
    response = requests.get(download_url, headers=headers, stream=True)
    response.raise_for_status()
    
    with output_path.open("wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    
    logger.info(f"Downloaded {output_path.stat().st_size / (1024*1024):.2f} MB")


def download_video(video_url: str, output_path) -> None:
    """
    Download the generated video file from a URL.
    
    Note: For Sora API, use download_video_from_sora() instead.
    This function is kept for compatibility with other video sources.
    """
    logger.info(f"Downloading video to {output_path.name}")
    
    with requests.get(video_url, stream=True) as r:
        r.raise_for_status()
        with output_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    
    logger.info(f"Downloaded {output_path.stat().st_size / (1024*1024):.2f} MB")

