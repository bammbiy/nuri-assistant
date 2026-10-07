"""The character's mind: personas, the Ollama client, the model/tool loop, reply parsing, memory and settings."""
from .brain import Companion, CompanionReply
from .llm import DEFAULT_MODEL, DEFAULT_OLLAMA_URL, OllamaClient, OllamaError, OllamaToolsUnsupported, ToolCall
from .memory import ConversationStore
from .personas import DEFAULT_PERSONA_ID, EXPRESSIONS, PERSONAS, Look, Persona, get_persona
from .reply import ReplyParser
from .settings import CompanionSettings, load_settings, save_settings
from .toolbox import ConfirmableAction, ConfirmingTools, ToolBox, parse_confirmation

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_OLLAMA_URL",
    "DEFAULT_PERSONA_ID",
    "EXPRESSIONS",
    "PERSONAS",
    "Companion",
    "CompanionReply",
    "CompanionSettings",
    "ConfirmableAction",
    "ConfirmingTools",
    "ConversationStore",
    "Look",
    "OllamaClient",
    "OllamaError",
    "OllamaToolsUnsupported",
    "Persona",
    "ReplyParser",
    "ToolBox",
    "ToolCall",
    "get_persona",
    "load_settings",
    "parse_confirmation",
    "save_settings",
]
