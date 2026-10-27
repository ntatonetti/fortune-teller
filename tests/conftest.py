import os
import sys
import tempfile
from pathlib import Path

# Tests never touch real services or the real guest log.
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["ELEVENLABS_API_KEY"] = ""
os.environ["PRINTER"] = "console"
os.environ["MEMORY_FILE"] = str(Path(tempfile.mkdtemp()) / "guests.json")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
