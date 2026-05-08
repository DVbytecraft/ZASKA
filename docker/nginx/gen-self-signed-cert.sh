#!/usr/bin/env bash
# Generates a self-signed SSL certificate for local/staging use.
# For production, replace with a real certificate (Let's Encrypt / ACM).
set -euo pipefail

CERT_DIR="$(dirname "$0")/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 \
  -newkey rsa:4096 \
  -keyout "$CERT_DIR/zaska.key" \
  -out    "$CERT_DIR/zaska.crt" \
  -days   365 \
  -nodes \
  -subj "/C=TG/ST=Lome/L=Lome/O=ZASKA/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:zaska.local,IP:127.0.0.1"

chmod 600 "$CERT_DIR/zaska.key"
echo "✓ Self-signed certificate generated in $CERT_DIR"
echo "  Certificate: $CERT_DIR/zaska.crt"
echo "  Private key: $CERT_DIR/zaska.key"
echo ""
echo "For production, replace with a valid certificate:"
echo "  certbot certonly --standalone -d yourdomain.com"
