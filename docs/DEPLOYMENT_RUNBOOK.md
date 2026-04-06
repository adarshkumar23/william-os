# WILLIAM OS Deployment Runbook (Task 6.7)

## Scope
- Oracle VM deployment
- TLS termination with Nginx + Let's Encrypt
- Monitoring and error tracking checks

## 1. Provision Oracle VM
- Ubuntu 24.04 LTS
- Open inbound ports: `22`, `80`, `443`

## 2. Install Runtime Dependencies
```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-plugin nginx certbot python3-certbot-nginx
sudo usermod -aG docker $USER
newgrp docker
```

## 3. Deploy Application
```bash
git clone https://github.com/adarshkumar23/william-os.git
cd william-os
cp .env.example .env
# Edit .env with production values and secrets

docker compose pull || true
docker compose up -d --build
```

## 4. Configure Nginx Reverse Proxy
- Use config: `infra/nginx/william-os.conf`
- Install into `/etc/nginx/sites-available/william-os`
- Enable site and test:
```bash
sudo ln -sf /etc/nginx/sites-available/william-os /etc/nginx/sites-enabled/william-os
sudo nginx -t
sudo systemctl reload nginx
```

## 5. Issue TLS Certificate
```bash
sudo certbot --nginx -d your-domain.example
```

## 6. Post-Deployment Validation
```bash
curl -I https://your-domain.example/health
curl -I https://your-domain.example/api/v1/auth/me
curl -s https://your-domain.example/health
```

Expected:
- HTTPS active
- security headers present
- health endpoint returns `status: ok`

## 7. Monitoring + Error Tracking
- Prometheus: scrape `/metrics`
- Grafana: verify dashboard datasource connectivity
- Sentry: set `SENTRY_DSN` and verify a captured test exception in non-prod

## 8. Rollback Procedure
```bash
git checkout <last-known-good-tag>
docker compose up -d --build
```

## 9. Production Checklist
- `ENVIRONMENT=production`
- strong `JWT_SECRET_KEY` (>= 32 bytes)
- strong DB/Redis credentials
- CORS restricted to real frontend domains
- TLS renewal cron active (`certbot renew --dry-run`)
