#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu 24.04 LTS host that will run self-hosted Documenso for the FLO_ESIGN.md
# synthetic test. Run as root (or via sudo) on the target host — never on the Windows dev machine.
#
#   scp -r deploy/documenso root@<host-ip>:/opt/documenso
#   ssh root@<host-ip> 'bash /opt/documenso/provision.sh'
#
# What this does, in order: installs Docker Engine + the Compose plugin from Docker's official apt repo
# (the documented, auditable method — not a curl|sh convenience script); opens only 22/80/443 in the
# firewall (3000 stays internal, reached only through the reverse proxy); generates a self-signed TEST
# PDF-signing certificate (cert.p12) — this is explicitly a development/test certificate, not a
# production-acceptable one; see FLO_ESIGN.md for what that means and the production decision still open.
# It does NOT start the stack — that's a separate, reviewable step (`docker compose up -d`) after `.env`
# is filled in from `.env.example`.
set -euo pipefail

echo "== Docker Engine + Compose plugin (official apt repo) =="
apt-get update -y
apt-get install -y ca-certificates curl gnupg ufw openssl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

echo "== Firewall: only SSH/HTTP/HTTPS reach this box; 3000 stays internal =="
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "== TEST PDF-signing certificate (self-signed — development/test only, see FLO_ESIGN.md) =="
CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "$CERT_DIR/cert.p12" ]; then
  if [ -z "${SIGNING_CERT_PASSPHRASE:-}" ]; then
    echo "Set SIGNING_CERT_PASSPHRASE before running (must match .env's SIGNING_CERT_PASSPHRASE)." >&2
    exit 1
  fi
  openssl req -x509 -newkey rsa:2048 -keyout /tmp/documenso-key.pem -out /tmp/documenso-cert.pem \
    -days 825 -nodes -subj "/CN=sign.lfprocessing.net (TEST - synthetic, not for production trust)"
  openssl pkcs12 -export -out "$CERT_DIR/cert.p12" \
    -inkey /tmp/documenso-key.pem -in /tmp/documenso-cert.pem \
    -passout "pass:${SIGNING_CERT_PASSPHRASE}"
  shred -u /tmp/documenso-key.pem /tmp/documenso-cert.pem
  chmod 600 "$CERT_DIR/cert.p12"
  echo "Wrote $CERT_DIR/cert.p12 (self-signed TEST certificate)."
else
  echo "$CERT_DIR/cert.p12 already exists; leaving it in place."
fi

cat <<'EOF'

Next (reviewable, not run automatically by this script):
  1. cp .env.example .env   and fill in real generated secrets (commands are inline as comments).
  2. Point DNS for sign.lfprocessing.net at this host's IP (still your decision — nothing here touches DNS).
  3. Install a reverse proxy for HTTPS (see Caddyfile in this directory) OR run behind an existing proxy.
  4. docker compose up -d
  5. docker compose logs -f documenso   — Documenso validates its own required env vars at boot; fix
     anything it reports missing before treating the deployment as ready.
EOF
