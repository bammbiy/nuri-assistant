"""Japanese voice through a local VOICEVOX-compatible engine: client, playback and the speaker thread."""
from .player import play_wav
from .speaker import VoiceSpeaker, VoiceStream
from .voicevox import ENGINES, Voice, VoiceError, VoicevoxClient

__all__ = ["ENGINES", "Voice", "VoiceError", "VoiceSpeaker", "VoiceStream", "VoicevoxClient", "play_wav"]
