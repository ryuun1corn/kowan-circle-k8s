#!/usr/bin/env bash
set -euo pipefail

# Generate a local CA + server + client certificates for mTLS.
# Usage:
#   ./04_gen_certs.sh <PUBLIC_IP_OR_DNS>
#
# Output:
#   certs/ca.crt, certs/ca.key
#   certs/server.crt, certs/server.key
#   certs/client.crt, certs/client.key, certs/client.p12

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <PUBLIC_IP_OR_DNS>"
  exit 1
fi

HOST="$1"
OUTDIR="$(dirname "$0")/../certs"
mkdir -p "$OUTDIR"

# 1) CA
openssl genrsa -out "$OUTDIR/ca.key" 4096
openssl req -x509 -new -nodes -key "$OUTDIR/ca.key" -sha256 -days 365 \
  -subj "/CN=circle-ca" -out "$OUTDIR/ca.crt"

# 2) Server cert with SAN (works for IP or DNS)
openssl genrsa -out "$OUTDIR/server.key" 2048

if [[ "$HOST" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  # Host is an IPv4 address
  cat > "$OUTDIR/server.ext" <<EOF
subjectAltName = IP:${HOST}
EOF
else
  # Host is a DNS name
  cat > "$OUTDIR/server.ext" <<EOF
subjectAltName = DNS:${HOST}
EOF
fi

openssl req -new -key "$OUTDIR/server.key" -subj "/CN=${HOST}" -out "$OUTDIR/server.csr"
openssl x509 -req -in "$OUTDIR/server.csr" -CA "$OUTDIR/ca.crt" -CAkey "$OUTDIR/ca.key" -CAcreateserial \
  -out "$OUTDIR/server.crt" -days 365 -sha256 -extfile "$OUTDIR/server.ext"

# 3) Client cert
openssl genrsa -out "$OUTDIR/client.key" 2048
openssl req -new -key "$OUTDIR/client.key" -subj "/CN=circle-user" -out "$OUTDIR/client.csr"
openssl x509 -req -in "$OUTDIR/client.csr" -CA "$OUTDIR/ca.crt" -CAkey "$OUTDIR/ca.key" -CAcreateserial \
  -out "$OUTDIR/client.crt" -days 365 -sha256

# Optional: bundle to PKCS#12 for easy browser import.
# You can set an empty export password with -passout pass:
openssl pkcs12 -export -out "$OUTDIR/client.p12" \
  -inkey "$OUTDIR/client.key" -in "$OUTDIR/client.crt" -certfile "$OUTDIR/ca.crt" \
  -passout pass:

echo "Generated certificates under: $OUTDIR"
echo "Client bundle for browser import: $OUTDIR/client.p12 (no export password)"
