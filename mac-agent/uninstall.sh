#!/bin/bash
PLIST_LABEL="com.personalassistant.macagent"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"

launchctl unload "$PLIST_DEST" 2>/dev/null && echo "Unloaded $PLIST_LABEL" || echo "Not loaded."
rm -f "$PLIST_DEST" && echo "Removed $PLIST_DEST"
