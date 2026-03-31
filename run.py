import warnings
import uvicorn
from backend.config import config

# Suppress noisy internal warnings from torch-based voice libraries (kokoro, faster-whisper)
warnings.filterwarnings("ignore", category=UserWarning, module="torch")
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")

if __name__ == "__main__":
    server = config.get("server", {})
    host = server.get("host", "0.0.0.0")
    port = server.get("port", 8000)
    print(f"Starting Personal Assistant at http://{host}:{port}")
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)
