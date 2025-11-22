import os
import logging
from pathlib import Path
from dataclasses import dataclass
import yaml

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration for video generation web app."""
    api_key: str  # OpenAI API key for prompt generation
    output_dir: Path
    
    @classmethod
    def from_yaml(cls, config_file: Path) -> "Config":
        """Load configuration from YAML file."""
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")
        
        with config_file.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # OpenAI API key for prompt generation
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("VIDEO_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY (or VIDEO_API_KEY) environment variable not set. "
                "Run: export OPENAI_API_KEY='your_key_here'"
            )
        
        # Output directory for uploads (defaults to uploads if not specified)
        output_dir = Path(data.get("output", {}).get("directory", "uploads"))
        
        return cls(
            api_key=api_key,
            output_dir=output_dir,
        )

