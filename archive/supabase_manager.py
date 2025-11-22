import logging
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)


def upload_image_to_supabase(config: Config, image_path: Path, filename: str) -> str:
    """
    Upload an image file to Supabase Storage and return public URL.
    
    Args:
        config: Configuration object with Supabase credentials
        image_path: Path to the image file
        filename: Filename to use in storage
    
    Returns:
        Public URL of the uploaded image
    
    Raises:
        RuntimeError: If upload fails due to permissions or other errors
    """
    from supabase import create_client
    
    logger.info(f"Uploading image to Supabase: {image_path.name}")
    
    if not image_path.exists():
        raise RuntimeError(f"Image file not found: {image_path}")
    
    supabase = create_client(config.supabase_url, config.supabase_key)
    
    try:
        with image_path.open("rb") as f:
            supabase.storage.from_(config.supabase_bucket).upload(filename, f, {"upsert": "true"})
    except Exception as e:
        error_msg = str(e)
        if "row-level security" in error_msg.lower() or "403" in error_msg or "unauthorized" in error_msg.lower():
            raise RuntimeError(
                f"Storage upload failed due to permissions. "
                f"This usually means you need to use SUPABASE_SERVICE_ROLE_KEY instead of SUPABASE_KEY. "
                f"Service role key bypasses Row Level Security policies. "
                f"Original error: {error_msg}"
            ) from e
        raise
    
    # Get public URL
    public_url = supabase.storage.from_(config.supabase_bucket).get_public_url(filename)
    
    logger.info(f"Image uploaded to: {public_url}")
    return public_url


def download_image_from_supabase(config: Config, filename: str, output_path: Path) -> None:
    """
    Download an image file from Supabase Storage using authenticated client.
    
    Args:
        config: Configuration object with Supabase credentials
        filename: Filename in storage
        output_path: Local path to save the downloaded image
    
    Raises:
        RuntimeError: If download fails
    """
    from supabase import create_client
    
    logger.debug(f"Downloading image from Supabase: {filename}")
    
    supabase = create_client(config.supabase_url, config.supabase_key)
    
    try:
        # Download file using authenticated client
        file_data = supabase.storage.from_(config.supabase_bucket).download(filename)
        
        with output_path.open("wb") as f:
            f.write(file_data)
        
        logger.debug(f"Downloaded image to: {output_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to download image from Supabase: {e}") from e


def upload_frame_to_supabase(config: Config, frame_path: Path, clip_number: int) -> str:
    """
    Upload extracted frame to Supabase Storage and return public URL.
    
    Args:
        config: Configuration object with Supabase credentials
        frame_path: Path to the frame image file
        clip_number: Clip number for naming
    
    Returns:
        Public URL of the uploaded frame
    """
    filename = f"frames/clip_{clip_number:02d}_frame.jpg"
    return upload_image_to_supabase(config, frame_path, filename)

