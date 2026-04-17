#!/bin/bash
# Run ON the Oracle VM after deploy.sh to wire up nginx
# Usage: bash scripts/setup-nginx-oracle.sh [your-domain.com]
set -euo pipefail

DOMAIN="${1:-}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Installing nginx config"
sudo cp "$REPO_DIR/infra/nginx/william-os.conf" /etc/nginx/sites-available/william-os
sudo ln -sf /etc/nginx/sites-available/william-os /etc/nginx/sites-enabled/william-os
sudo rm -f /etc/nginx/sites-enabled/default

# Open port 8080 in iptables (no-SSL fallback for testing by IP)
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8080 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || true

if [ -n "$DOMAIN" ]; then
  echo "==> Setting up SSL with Let's Encrypt for $DOMAIN"
  # Replace placeholder in config
  sudo sed -i "s/DOMAIN/$DOMAIN/g" /etc/nginx/sites-available/william-os
  sudo sed -i "s/server_name _;/server_name $DOMAIN;/g" /etc/nginx/sites-available/william-os

  # Obtain cert (nginx plugin handles reload)
  sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m adarshkr2375@gmail.com
else
  echo "==> No domain provided — disabling the HTTPS server block (IP-only mode on :8080)"
  # Comment out the ssl server block so nginx starts without certs
  sudo python3 - <<'PYEOF'
import re, pathlib
p = pathlib.Path("/etc/nginx/sites-available/william-os")
txt = p.read_text()
# Remove the HTTPS block that requires certs
txt = re.sub(r'# HTTPS.*?^}', '', txt, flags=re.DOTALL|re.MULTILINE)
p.write_text(txt)
PYEOF
fi

sudo nginx -t && sudo systemctl reload nginx
echo "✅ Nginx ready."
if [ -n "$DOMAIN" ]; then
  echo "   https://$DOMAIN"
else
  echo "   http://<vm-ip>:8080  (no-SSL fallback)"
  echo "   http://<vm-ip>:8000  (backend direct)"
  echo "   http://<vm-ip>:3000  (frontend direct)"
fi
