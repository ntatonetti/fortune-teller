import os
import sys
import tempfile
from pathlib import Path

# Tests never touch real services or the real guest log (test_server.py
# swaps the clients for fakes; these keys just let the server start).
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["ELEVENLABS_API_KEY"] = "test-key"
os.environ["ELEVENLABS_VOICE_ID"] = "test-voice"
os.environ["PRINTER"] = "console"
os.environ["MEMORY_FILE"] = str(Path(tempfile.mkdtemp()) / "guests.json")
os.environ["ORACLE_ENV_FILE"] = str(Path(tempfile.mkdtemp()) / ".env")  # not your .env: defaults only
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
