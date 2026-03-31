import sys
from pathlib import Path

if not Path("config.yaml").exists():
    print("config.yaml not found. Run setup first:")
    print("  python setup.py")
    sys.exit(1)

import uvicorn
from backend.config import config

if __name__ == "__main__":
    host = config["server"]["host"]
    port = config["server"]["port"]
    print(f"Starting Home Assistant at http://{host}:{port}")
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)
