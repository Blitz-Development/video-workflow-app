import logging
import subprocess
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def run_ffmpeg(args: List[str]) -> None:
    """Run an ffmpeg command and raise if it fails."""
    cmd = ["ffmpeg", "-y"] + args  # -y = overwrite without asking
    logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logger.error(f"ffmpeg stderr: {result.stderr}")
        raise RuntimeError("ffmpeg command failed")


def strip_audio(input_video: Path, output_video: Path) -> None:
    """Create a silent version of the video (no audio track)."""
    logger.info(f"Stripping audio: {input_video.name} → {output_video.name}")
    run_ffmpeg([
        "-i", str(input_video),
        "-c", "copy",
        "-an",  # remove audio
        str(output_video),
    ])


def extract_last_frame(input_video: Path, output_image: Path) -> None:
    """Extract the last frame of a video as an image."""
    logger.info(f"Extracting last frame from {input_video.name}")
    run_ffmpeg([
        "-sseof", "-0.05",  # ~last 0.05 seconds
        "-i", str(input_video),
        "-frames:v", "1",
        "-q:v", "2",  # quality
        str(output_image),
    ])


def concat_videos(video_files: List[Path], output_video: Path) -> None:
    """Concatenate multiple videos into one using ffmpeg concat demuxer."""
    logger.info(f"Concatenating {len(video_files)} videos into {output_video.name}")
    
    list_file = output_video.parent / "list.txt"
    with list_file.open("w", encoding="utf-8") as f:
        for vf in video_files:
            f.write(f"file '{vf.name}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file.name),
        "-c", "copy",
        str(output_video.name),
    ]
    
    logger.debug(f"Running (from {output_video.parent}): {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=output_video.parent, stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logger.error(f"ffmpeg concat stderr: {result.stderr}")
        raise RuntimeError("ffmpeg concat failed")

