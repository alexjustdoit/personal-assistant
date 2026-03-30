import uvicorn
from backend.config import config

if __name__ == "__main__":
    host = config["server"]["host"]
    port = config["server"]["port"]
    print(f"Starting Home Assistant at http://{host}:{port}")
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)
