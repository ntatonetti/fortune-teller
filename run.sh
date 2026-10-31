kill $(lsof -t -iTCP:8000 -sTCP:LISTEN)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m server
