import json
import logging
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
import uuid

logger = logging.getLogger(__name__)


@dataclass
class SessionData:
    """Session data structure."""
    session_id: str
    scene_description: str
    starting_image_path: str
    prompts: List[str]
    current_step: int
    uploaded_videos: List[str]  # Paths to uploaded videos
    last_frames: List[str]  # Paths to last frames
    num_clips: int
    openai_api_key: str  # User's OpenAI API key (stored in session only)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        # Don't save API key to disk for security
        data = asdict(self)
        data.pop('openai_api_key', None)  # Remove API key before saving
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionData":
        """Create from dictionary."""
        # API key won't be in saved data, so provide empty string
        if 'openai_api_key' not in data:
            data['openai_api_key'] = ''
        return cls(**data)


class SessionManager:
    """Manages session state for the web app."""
    
    def __init__(self, sessions_dir: Path = Path("sessions")):
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(exist_ok=True)
        self._in_memory_sessions: Dict[str, SessionData] = {}
    
    def create_session(
        self,
        scene_description: str,
        starting_image_path: str,
        prompts: List[str],
        num_clips: int,
        openai_api_key: str
    ) -> str:
        """Create a new session and return session ID."""
        session_id = str(uuid.uuid4())
        
        session_data = SessionData(
            session_id=session_id,
            scene_description=scene_description,
            starting_image_path=starting_image_path,
            prompts=prompts,
            current_step=1,
            uploaded_videos=[],
            last_frames=[],
            num_clips=num_clips,
            openai_api_key=openai_api_key
        )
        
        self._in_memory_sessions[session_id] = session_data
        self._save_session(session_data)
        
        logger.info(f"Created session {session_id} with {len(prompts)} prompts")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get session data by ID."""
        # Check in-memory first
        if session_id in self._in_memory_sessions:
            return self._in_memory_sessions[session_id]
        
        # Try to load from file
        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            try:
                with session_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                session_data = SessionData.from_dict(data)
                self._in_memory_sessions[session_id] = session_data
                return session_data
            except Exception as e:
                logger.error(f"Failed to load session {session_id}: {e}")
                return None
        
        return None
    
    def update_session(self, session_id: str, **updates) -> bool:
        """Update session data."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        # Update fields
        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        self._in_memory_sessions[session_id] = session
        self._save_session(session)
        return True
    
    def add_uploaded_video(self, session_id: str, video_path: str, frame_path: str) -> bool:
        """Add an uploaded video and its extracted frame to the session."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.uploaded_videos.append(video_path)
        session.last_frames.append(frame_path)
        
        # Move to next step if not the last one
        if session.current_step < session.num_clips:
            session.current_step += 1
        
        self._in_memory_sessions[session_id] = session
        self._save_session(session)
        return True
    
    def get_current_image_path(self, session_id: str) -> Optional[str]:
        """Get the starting image path for the current step."""
        session = self.get_session(session_id)
        if not session:
            return None
        
        # First step uses starting image
        if session.current_step == 1:
            return session.starting_image_path
        
        # Subsequent steps use last frame from previous video
        if session.current_step > 1 and len(session.last_frames) >= session.current_step - 1:
            return session.last_frames[session.current_step - 2]
        
        return None
    
    def is_complete(self, session_id: str) -> bool:
        """Check if all videos have been uploaded."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        return len(session.uploaded_videos) >= session.num_clips
    
    def _save_session(self, session_data: SessionData) -> None:
        """Save session to file (API key is NOT saved for security)."""
        session_file = self.sessions_dir / f"{session_data.session_id}.json"
        try:
            # to_dict() already removes the API key
            with session_file.open("w", encoding="utf-8") as f:
                json.dump(session_data.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save session {session_data.session_id}: {e}")

