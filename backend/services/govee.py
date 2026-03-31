"""
Govee Developer API (v1) client.
Rate limit: ~100 requests/day on the free tier — device list is cached in memory.
"""

import httpx
from datetime import datetime, timedelta
from backend.config import config

_BASE = "https://developer-api.govee.com/v1"

# Common color name → RGB mapping
COLOR_MAP = {
    "red": (255, 0, 0),
    "green": (0, 200, 50),
    "blue": (0, 100, 255),
    "white": (255, 255, 255),
    "warm white": (255, 200, 100),
    "cool white": (200, 220, 255),
    "yellow": (255, 220, 0),
    "orange": (255, 120, 0),
    "purple": (160, 0, 255),
    "pink": (255, 60, 160),
    "cyan": (0, 220, 220),
    "teal": (0, 180, 160),
    "magenta": (255, 0, 200),
    "indigo": (75, 0, 130),
    "lavender": (180, 130, 255),
    "lime": (140, 255, 0),
    "coral": (255, 100, 80),
    "turquoise": (64, 224, 208),
    "off": None,
}

_device_cache: list[dict] = []
_cache_expires: datetime | None = None
_CACHE_TTL = timedelta(hours=1)


def _api_key() -> str:
    return config.get("govee", {}).get("api_key", "")


def govee_enabled() -> bool:
    return bool(_api_key())


def _headers() -> dict:
    return {"Govee-API-Key": _api_key(), "Content-Type": "application/json"}


async def get_devices(force_refresh: bool = False) -> list[dict]:
    """Return cached device list; refresh from API if stale or forced."""
    global _device_cache, _cache_expires
    if not force_refresh and _cache_expires and datetime.utcnow() < _cache_expires and _device_cache:
        return _device_cache
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{_BASE}/devices", headers=_headers(), timeout=10)
            res.raise_for_status()
            devices = res.json().get("data", {}).get("devices", [])
        _device_cache = devices
        _cache_expires = datetime.utcnow() + _CACHE_TTL
        return devices
    except Exception:
        return _device_cache  # return stale cache on error


async def control_device(device_id: str, model: str, cmd_name: str, cmd_value) -> bool:
    """Send a control command to a specific device. Returns True on success."""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.put(
                f"{_BASE}/devices/control",
                headers=_headers(),
                json={"device": device_id, "model": model, "cmd": {"name": cmd_name, "value": cmd_value}},
                timeout=10,
            )
            return res.status_code == 200
    except Exception:
        return False


def find_devices(name_hint: str, devices: list[dict]) -> list[dict]:
    """Find devices whose deviceName contains the hint (case-insensitive). 'all' returns all."""
    if name_hint.lower() in ("all", "all lights", "all devices", "everything"):
        return devices
    hint = name_hint.lower()
    return [d for d in devices if hint in d.get("deviceName", "").lower()]


def color_name_to_rgb(name: str) -> tuple[int, int, int] | None:
    return COLOR_MAP.get(name.lower().strip())


def supports_cmd(device: dict, cmd: str) -> bool:
    return cmd in device.get("supportCmds", [])


async def execute_govee_intent(intent: dict) -> str:
    """
    Execute a Govee intent dict and return a human-readable result string
    for injection into the system prompt.
    """
    devices = await get_devices()
    if not devices:
        return "[Govee] No devices found or API unreachable."

    action = intent.get("action")
    device_hint = intent.get("device", "all")
    targets = find_devices(device_hint, devices)

    if not targets:
        names = ", ".join(d.get("deviceName", "?") for d in devices)
        return f'[Govee] No device matching "{device_hint}". Available: {names}'

    results = []
    for dev in targets:
        did, model, dname = dev["device"], dev["model"], dev.get("deviceName", dev["device"])

        if action == "on":
            ok = await control_device(did, model, "turn", "on")
            results.append(f'{"✓" if ok else "✗"} {dname}: turned on')

        elif action == "off":
            ok = await control_device(did, model, "turn", "off")
            results.append(f'{"✓" if ok else "✗"} {dname}: turned off')

        elif action == "brightness":
            level = max(0, min(100, int(intent.get("brightness", 100))))
            if supports_cmd(dev, "brightness"):
                ok = await control_device(did, model, "brightness", level)
                results.append(f'{"✓" if ok else "✗"} {dname}: brightness → {level}%')
            else:
                results.append(f'✗ {dname}: brightness not supported')

        elif action == "color":
            color_str = str(intent.get("color", "white"))
            rgb = color_name_to_rgb(color_str)
            if rgb is None:
                # Try to parse "r,g,b" format
                try:
                    parts = [int(x) for x in color_str.split(",")]
                    rgb = (parts[0], parts[1], parts[2])
                except Exception:
                    results.append(f'✗ {dname}: unknown color "{color_str}"')
                    continue
            if supports_cmd(dev, "color"):
                ok = await control_device(did, model, "color", {"r": rgb[0], "g": rgb[1], "b": rgb[2]})
                results.append(f'{"✓" if ok else "✗"} {dname}: color → {color_str}')
            else:
                results.append(f'✗ {dname}: color not supported')

        elif action == "color_temp":
            kelvin = int(intent.get("color_temp", 4000))
            if supports_cmd(dev, "colorTem"):
                ok = await control_device(did, model, "colorTem", kelvin)
                results.append(f'{"✓" if ok else "✗"} {dname}: color temp → {kelvin}K')
            else:
                results.append(f'✗ {dname}: color temperature not supported')

    summary = "\n".join(results)
    return f"[Govee] Results:\n{summary}\nConfirm these actions to the user naturally."
