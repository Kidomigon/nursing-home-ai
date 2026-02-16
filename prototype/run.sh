#!/bin/bash
# Room Companion — launch with HTTPS
cd "$(dirname "$0")"

# Clean environment (avoid Maestro AppImage LD_LIBRARY_PATH conflicts)
unset LD_LIBRARY_PATH

# Activate virtualenv if present
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

# Generate self-signed certs if needed
python3 -c "from main import ensure_certs; ensure_certs()"

echo "Starting Room Companion on https://0.0.0.0:8000"
echo "Default admin login: admin / admin1234"
echo ""

uvicorn main:app --host 0.0.0.0 --port 8000 \
    --ssl-keyfile certs/server.key --ssl-certfile certs/server.crt
