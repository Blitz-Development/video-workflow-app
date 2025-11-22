#!/usr/bin/env python3
"""
Generate AI video stories by orchestrating:
1. Image upload to Supabase
2. AI prompt generation (XAI Grok)
3. Video generation from image + prompt
4. Frame extraction and uploading
5. Video processing and concatenation
"""

import logging
from pathlib import Path
from typing import List

from config import Config
from supabase_manager import upload_image_to_supabase, upload_frame_to_supabase
from prompt_generator import generate_clip_plan
from video_generator import call_generate_video_api, poll_video_status, download_video_from_sora
from video_processor import strip_audio, extract_last_frame, concat_videos


# =============================
# LOGGING SETUP
# =============================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    config_file = Path(__file__).parent / "config.yaml"
    
    try:
        config = Config.from_yaml(config_file)
    except (FileNotFoundError, RuntimeError) as e:
        logger.error(f"Configuration error: {e}")
        return 1

    config.output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {config.output_dir.resolve()}")

    # -------------------------
    # UPLOAD INITIAL IMAGE
    # -------------------------
    
    current_image_url = config.starting_image_url
    
    if config.starting_image_path:
        local_image = Path(config.starting_image_path)
        if not local_image.is_absolute():
            local_image = Path(__file__).parent / config.starting_image_path
        
        if local_image.exists():
            try:
                current_image_url = upload_image_to_supabase(config, local_image, "initial_image.jpg")
                logger.info(f"Initial image uploaded to Supabase")
            except Exception as e:
                logger.error(f"Failed to upload initial image: {e}")
                raise
        else:
            logger.error(f"Starting image file not found: {local_image}")
            raise FileNotFoundError(f"Starting image file not found: {local_image}")
    elif not current_image_url:
        raise RuntimeError("No starting image provided (neither URL nor local path)")

    # -------------------------
    # GENERATE PROMPTS
    # -------------------------
    
    prompts = generate_clip_plan(config, config.scene_description, config.num_clips)
    silent_clips: List[Path] = []

    # -------------------------
    # GENERATE CLIPS
    # -------------------------

    for i, prompt in enumerate(prompts, start=1):
        logger.info("=" * 60)
        logger.info(f"Generating clip {i}/{len(prompts)}")
        logger.info("=" * 60)

        try:
            # Generate video (returns video ID)
            video_id = call_generate_video_api(
                config=config,
                prompt=prompt,
                image_url=current_image_url,
            )

            # Poll for completion
            status_data = poll_video_status(config, video_id)

            # Download video directly from Sora API using download endpoint
            raw_clip_path = config.output_dir / f"clip_{i:02d}.mp4"
            download_video_from_sora(config, video_id, raw_clip_path)

            # Process: strip audio
            silent_clip_path = config.output_dir / f"clip_{i:02d}_silent.mp4"
            strip_audio(raw_clip_path, silent_clip_path)
            silent_clips.append(silent_clip_path)

            # Extract last frame
            last_frame_path = config.output_dir / f"clip_{i:02d}_last_frame.jpg"
            extract_last_frame(silent_clip_path, last_frame_path)

            # Auto-chain frames if enabled: use last frame as next clip's starting image
            if config.auto_chain_frames and i < config.num_clips:
                try:
                    current_image_url = upload_frame_to_supabase(config, last_frame_path, i)
                except Exception as e:
                    logger.warning(f"Failed to upload frame for chaining: {e}. Using previous image.")
            else:
                logger.info(f"Extracted last frame: {last_frame_path.name}")

        except Exception as e:
            logger.error(f"Error generating clip {i}: {e}")
            raise

    # -------------------------
    # CONCATENATE CLIPS
    # -------------------------

    logger.info("=" * 60)
    logger.info("Concatenating all silent clips into final_output.mp4")
    logger.info("=" * 60)

    final_output = config.output_dir / "final_output.mp4"
    concat_videos(silent_clips, final_output)

    logger.info(f"✓ Done. Final video: {final_output.resolve()}")
    return 0


if __name__ == "__main__":
    exit(main())

