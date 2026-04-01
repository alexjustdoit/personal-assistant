import warnings
import uvicorn
from backend.config import config

# Suppress noisy internal warnings from torch-based voice libraries (kokoro, faster-whisper)
warnings.filterwarnings("ignore", category=UserWarning, module="torch")
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")


def free_port(port: int):
    """Kill any process already bound to `port` so we can start cleanly."""
    import psutil
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr.port == port and conn.pid:
            try:
                psutil.Process(conn.pid).kill()
                print(f"Killed stale process {conn.pid} on port {port}")
            except Exception:
                pass


if __name__ == "__main__":
    server = config.get("server", {})
    host = server.get("host", "0.0.0.0")
    port = server.get("port", 8000)
    free_port(port)
    print(f"Starting Personal Assistant at http://{host}:{port}")
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)
