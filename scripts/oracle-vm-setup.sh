#!/bin/bash
# Run this ONCE on a fresh Oracle Cloud Ubuntu 22.04 VM
# Usage: bash oracle-vm-setup.sh
set -euo pipefail

echo "==> Updating system packages"
sudo apt-get update -q && sudo apt-get upgrade -y -q

echo "==> Installing Docker"
sudo apt-get install -y -q ca-certificates curl gnupg lsb-release
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -q
sudo apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "==> Adding ubuntu user to docker group"
sudo usermod -aG docker ubuntu
newgrp docker || true

echo "==> Installing nginx + certbot"
sudo apt-get install -y -q nginx certbot python3-certbot-nginx

echo "==> Opening Oracle firewall ports (iptables)"
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || sudo apt-get install -y -q iptables-persistent && sudo netfilter-persistent save

echo "==> Cloning william-os repo"
if [ ! -d /opt/william-os ]; then
  sudo git clone https://github.com/adarshkumar23/william-os.git /opt/william-os
  sudo chown -R ubuntu:ubuntu /opt/william-os
else
  echo "Repo already exists, skipping clone"
fi

echo ""
echo "✅ VM setup complete. Next:"
echo "   1. cd /opt/william-os"
echo "   2. cp .env.example .env && nano .env  (fill JWT_SECRET_KEY, etc.)"
echo "   3. bash scripts/deploy.sh"
