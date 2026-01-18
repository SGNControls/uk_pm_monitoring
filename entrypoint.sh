#!/bin/bash
# Railway entrypoint script
set -e

# Default port if not set
PORT=${PORT:-8000}

echo "Starting application on port $PORT"

# Start gunicorn with the correct port
exec gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT app:app
