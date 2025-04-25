#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "--- Deploying Application Service ---"

# Define source and destination paths
SOURCE_SERVICE_FILE="arc_app.service"
DEST_SERVICE_FILE="/etc/systemd/system/arc_app.service" # Standard location for systemd unit files

# Check if source file exists
if [ ! -f "$SOURCE_SERVICE_FILE" ]; then
    echo "Error: Source service file '$SOURCE_SERVICE_FILE' not found in current directory."
    exit 1
fi

echo "Copying '$SOURCE_SERVICE_FILE' to '$DEST_SERVICE_FILE'..."
sudo cp "$SOURCE_SERVICE_FILE" "$DEST_SERVICE_FILE"

echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "Restarting arc_app service..."
sudo systemctl restart arc_app.service

echo "Checking service status (last few lines)..."
sudo systemctl status arc_app.service --no-pager | tail -n 5 # Show recent status lines

echo "Application service deployment script finished successfully."
echo "---------------------------------------"
