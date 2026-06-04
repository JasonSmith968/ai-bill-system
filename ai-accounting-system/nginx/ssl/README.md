# SSL Certificates

Place your SSL certificate files in this directory:

- `cert.pem` — Full chain certificate (server cert + intermediate CA)
- `key.pem` — Private key

## Using Let's Encrypt (Recommended)

```bash
# Install certbot
apt install certbot

# Generate certificate
certbot certonly --standalone -d your-domain.com

# Copy certificates
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/cert.pem
cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/key.pem

# Auto-renewal (add to crontab)
0 3 * * * certbot renew --quiet && docker compose -f docker-compose.prod.yml restart nginx
```

## Using Self-Signed (Development/Testing)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem \
  -subj "/C=CN/ST=Beijing/L=Beijing/O=AI Accounting/CN=localhost"
```

## Security

- NEVER commit certificate files to version control
- The `.gitignore` already excludes `nginx/ssl/*.pem` and `nginx/ssl/*.key`
- Set file permissions: `chmod 600 nginx/ssl/key.pem`
