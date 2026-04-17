#!/bin/bash
# Push code + deploy to Oracle VM from your local machine
# Usage: bash scripts/remote-deploy.sh <vm-ip> <ssh-key-path>
#   e.g. bash scripts/remote-deploy.sh 152.70.x.x ~/.ssh/oracle_key.pem
set -euo pipefail

VM_IP="${1:?Usage: remote-deploy.sh <vm-ip> <ssh-key-path>}"
KEY="${2:?Usage: remote-deploy.sh <vm-ip> <ssh-key-path>}"
VM_USER="ubuntu"
REMOTE="/opt/william-os"
LOCAL_ENV=".env"

SSH="ssh -i $KEY -o StrictHostKeyChecking=no $VM_USER@$VM_IP"
SCP="scp -i $KEY -o StrictHostKeyChecking=no"

echo "==> Connecting to $VM_IP"

# ── First-time VM setup if docker is missing ─────────────────────
if ! $SSH "command -v docker" &>/dev/null; then
  echo "==> Docker not found — running oracle-vm-setup.sh"
  $SCP scripts/oracle-vm-setup.sh "$VM_USER@$VM_IP:/tmp/oracle-vm-setup.sh"
  $SSH "bash /tmp/oracle-vm-setup.sh"
fi

# ── Ensure repo exists ───────────────────────────────────────────
$SSH "if [ ! -d $REMOTE ]; then sudo git clone https://github.com/adarshkumar23/william-os.git $REMOTE && sudo chown -R ubuntu:ubuntu $REMOTE; fi"

# ── Upload .env ──────────────────────────────────────────────────
if [ -f "$LOCAL_ENV" ]; then
  echo "==> Uploading .env"
  $SCP "$LOCAL_ENV" "$VM_USER@$VM_IP:$REMOTE/.env"
else
  echo "WARNING: No local .env found — make sure .env exists on the VM"
fi

# ── Pull latest code ─────────────────────────────────────────────
echo "==> Pulling latest code on VM"
$SSH "cd $REMOTE && git fetch origin && git checkout main && git pull origin main"

# ── Run deploy ───────────────────────────────────────────────────
echo "==> Running deploy script on VM"
$SSH "cd $REMOTE && bash scripts/deploy.sh"

echo ""
echo "✅ Done. Visit http://$VM_IP:8000/health"
