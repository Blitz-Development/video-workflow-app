import json
import logging
import requests
from typing import List
from config import Config

logger = logging.getLogger(__name__)


def call_openai_gpt(api_key: str, scene_description: str, num_clips: int) -> List[str]:
    """
    Use OpenAI GPT to generate intelligent clip prompts from a scene description.
    
    Uses the provided API key. Cheap & fast model (gpt-4o-mini).
    Returns a list of num_clips prompts, each describing a distinct scene progression.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    system_prompt = (
        "You are a creative video scriptwriter. Your job is to break down a scene description "
        "into distinct, sequential video clips. Each clip should build on the previous one, "
        "creating a coherent story progression. Return ONLY a JSON array of strings with no markdown."
    )
    
    user_message = (
        f"Break this scene into {num_clips} distinct, sequential video clip prompts. "
        f"Each prompt should be 1-2 sentences and build on the previous one. "
        f"Return as a JSON array of exactly {num_clips} strings, nothing else.\n\n"
        f"Scene: {scene_description}"
    )
    
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "model": "gpt-4o-mini",  # Fast, cheap model
        "temperature": 0.7,
    }
    
    logger.info(f"Calling OpenAI GPT to plan {num_clips} clips")
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload,
    )
    
    if not response.ok:
        raise RuntimeError(
            f"OpenAI API request failed: {response.status_code} {response.text}"
        )
    
    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    if not content:
        raise RuntimeError("No content from OpenAI API")
    
    try:
        # Parse JSON from response (may have markdown fencing)
        content_clean = content.strip()
        if content_clean.startswith("```"):
            content_clean = content_clean.split("```")[1]
            if content_clean.startswith("json"):
                content_clean = content_clean[4:]
        content_clean = content_clean.strip()
        
        prompts = json.loads(content_clean)
        
        if not isinstance(prompts, list) or len(prompts) != num_clips:
            raise ValueError(f"Expected list of {num_clips} prompts, got {len(prompts) if isinstance(prompts, list) else 'not a list'}")
        
        logger.info(f"Generated {len(prompts)} intelligent prompts")
        for i, prompt in enumerate(prompts, start=1):
            logger.debug(f"  Clip {i}: {prompt}")
        
        return prompts
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI response as JSON: {content}")
        raise RuntimeError(f"OpenAI response was not valid JSON: {e}")


def generate_clip_plan(api_key: str, scene_description: str, num_clips: int) -> List[str]:
    """
    Generate prompts for each clip using OpenAI GPT.
    
    Falls back to simple splitting if GPT fails.
    
    Args:
        api_key: OpenAI API key
        scene_description: Description of the scene
        num_clips: Number of clips to generate
    """
    try:
        return call_openai_gpt(api_key, scene_description, num_clips)
    except Exception as e:
        logger.warning(f"OpenAI planning failed, falling back to simple splitting: {e}")
    
    # Fallback: simple sequential prompts
    prompts = []
    for i in range(num_clips):
        prompts.append(f"{scene_description} (deel {i+1} van {num_clips})")
    return prompts

