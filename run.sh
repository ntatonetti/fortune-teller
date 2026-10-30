python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
[ -f .env ] || cp .env.example .env   # first run only; then fill in the Claude and ElevenLabs keys
.venv/bin/python -m server
