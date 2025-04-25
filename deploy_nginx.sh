#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "--- Deploying Nginx Configuration ---"

# Define source and destination paths
SOURCE_NGINX_CONF="nginx.txt"
DEST_NGINX_CONF="/etc/nginx/sites-available/metaskepsis" # Assuming this is your target file name

# Check if source file exists
if [ ! -f "$SOURCE_NGINX_CONF" ]; then
    echo "Error: Source Nginx config file '$SOURCE_NGINX_CONF' not found in current directory."
    exit 1
fi

echo "Copying '$SOURCE_NGINX_CONF' to '$DEST_NGINX_CONF'..."
sudo cp "$SOURCE_NGINX_CONF" "$DEST_NGINX_CONF"

echo "Testing Nginx configuration..."
sudo nginx -t

echo "Reloading Nginx service..."
sudo systemctl reload nginx

echo "Nginx deployment script finished successfully."
echo "---------------------------------------"
