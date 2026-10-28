import os
import socket
import sys

import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    # An old oracle still holding the port would keep answering the browser
    # with its old settings, so refuse to start quietly next to it.
    with socket.socket() as s:
        if s.connect_ex((host, port)) == 0:
            sys.exit(
                f"\n  Another server is already running on port {port}, so this one can't start.\n"
                f"  Stop it with:  kill $(lsof -t -iTCP:{port} -sTCP:LISTEN)\n"
                f"  (or run this one elsewhere:  PORT=8001 .venv/bin/python -m server)\n"
            )
    uvicorn.run("server.app:app", host=host, port=port, log_level="info")
