import uvicorn
from backend.config import config

if __name__ == "__main__":
    server = config.get("server", {})
    host = server.get("host", "0.0.0.0")
    port = server.get("port", 8000)
    print(f"Starting Home Assistant at http://{host}:{port}")
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)
