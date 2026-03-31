#!/bin/bash
# Install the Mac Activity Agent as a launchd user agent.
# Runs agent.py every 30 minutes automatically.
#
# Usage:
#   1. cp config.yaml.example config.yaml && edit config.yaml
#   2. pip3 install pyyaml
#   3. chmod +x install.sh && ./install.sh
#
# Logs: /tmp/pa-mac-agent.log
# To uninstall: ./uninstall.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_PY="$SCRIPT_DIR/agent.py"
CONFIG_YAML="$SCRIPT_DIR/config.yaml"
PLIST_LABEL="com.personalassistant.macagent"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
LOG_FILE="/tmp/pa-mac-agent.log"

if [ ! -f "$CONFIG_YAML" ]; then
    echo "Error: config.yaml not found. Copy config.yaml.example to config.yaml and edit it first."
    exit 1
fi

PYTHON=$(which python3)
if [ -z "$PYTHON" ]; then
    echo "Error: python3 not found in PATH."
    exit 1
fi

# Read interval from config (default 30 min = 1800 sec)
INTERVAL_MIN=$("$PYTHON" -c "
import yaml, sys
with open('$CONFIG_YAML') as f:
    c = yaml.safe_load(f)
print(c.get('poll_interval_minutes', 30))
" 2>/dev/null || echo 30)
INTERVAL_SEC=$((INTERVAL_MIN * 60))

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$AGENT_PY</string>
    </array>
    <key>StartInterval</key>
    <integer>$INTERVAL_SEC</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_FILE</string>
    <key>StandardErrorPath</key>
    <string>$LOG_FILE</string>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
</dict>
</plist>
EOF

# Unload first if already loaded (ignore errors)
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo ""
echo "Installed and started: $PLIST_LABEL"
echo "Runs every ${INTERVAL_MIN} minutes."
echo "Logs: $LOG_FILE"
echo ""
echo "NOTE: Safari history requires Full Disk Access for Terminal (or your Python binary)."
echo "System Settings → Privacy & Security → Full Disk Access → add Terminal"
