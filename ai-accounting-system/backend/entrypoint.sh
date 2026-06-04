#!/bin/bash
set -e

echo "========================================="
echo "  AI Smart Accounting System - Backend"
echo "========================================="

# Wait for MySQL to be ready
echo "[entrypoint] Waiting for MySQL..."
python -c "
import time, os, pymysql
from urllib.parse import urlparse

db_url = os.environ.get('DATABASE_URL', '')
if not db_url:
    print('[entrypoint] No DATABASE_URL set, skipping wait')
    exit(0)

parsed = urlparse(db_url.replace('mysql+pymysql', 'mysql'))
host = parsed.hostname or 'localhost'
port = parsed.port or 3306

for i in range(30):
    try:
        conn = pymysql.connect(host=host, port=port,
                               user=parsed.username or 'root',
                               password=parsed.password or '',
                               database=parsed.path.lstrip('/'))
        conn.close()
        print(f'[entrypoint] MySQL ready at {host}:{port}')
        break
    except Exception:
        print(f'[entrypoint] Waiting for MySQL... ({i+1}/30)')
        time.sleep(2)
else:
    print('[entrypoint] MySQL not ready after 60s, continuing anyway...')
"

# Initialize database (create tables + default data)
echo "[entrypoint] Initializing database..."
python -c "
import os
from app import create_app
from extensions import db
from models.user import User
from models.transaction import Category
import models

app = create_app()
with app.app_context():
    # Try migrations first, fall back to create_all
    try:
        from flask_migrate import upgrade
        upgrade()
        print('[entrypoint] Migrations applied successfully')
    except Exception as e:
        print(f'[entrypoint] Migration failed or no migrations: {e}')
        db.create_all()
        print('[entrypoint] Tables created via create_all()')

    # Default categories
    default_categories = [
        {'name': '餐饮', 'type': 'expense', 'icon': 'utensils', 'color': '#EF4444'},
        {'name': '交通', 'type': 'expense', 'icon': 'car', 'color': '#F59E0B'},
        {'name': '购物', 'type': 'expense', 'icon': 'shopping-bag', 'color': '#8B5CF6'},
        {'name': '娱乐', 'type': 'expense', 'icon': 'gamepad', 'color': '#EC4899'},
        {'name': '住房', 'type': 'expense', 'icon': 'home', 'color': '#3B82F6'},
        {'name': '医疗', 'type': 'expense', 'icon': 'hospital', 'color': '#10B981'},
        {'name': '教育', 'type': 'expense', 'icon': 'book', 'color': '#6366F1'},
        {'name': '通讯', 'type': 'expense', 'icon': 'phone', 'color': '#14B8A6'},
        {'name': '其他', 'type': 'expense', 'icon': 'tag', 'color': '#6B7280'},
        {'name': '工资', 'type': 'income', 'icon': 'money-bill', 'color': '#22C55E'},
        {'name': '奖金', 'type': 'income', 'icon': 'gift', 'color': '#F59E0B'},
        {'name': '投资', 'type': 'income', 'icon': 'chart-line', 'color': '#3B82F6'},
        {'name': '兼职', 'type': 'income', 'icon': 'briefcase', 'color': '#8B5CF6'},
        {'name': '红包', 'type': 'income', 'icon': 'envelope', 'color': '#EF4444'},
        {'name': '其他', 'type': 'income', 'icon': 'tag', 'color': '#6B7280'},
    ]
    for cat in default_categories:
        if not Category.query.filter_by(name=cat['name'], type=cat['type']).first():
            db.session.add(Category(**cat, is_default=True))

    # Admin user (password from env, auto-generate if not set)
    import secrets, string as _string
    admin_password = os.environ.get('ADMIN_PASSWORD', '')
    if not admin_password:
        admin_password = ''.join(secrets.choice(_string.ascii_letters + _string.digits + '!@#') for _ in range(16))
        print(f'[entrypoint] WARNING: ADMIN_PASSWORD not set. Generated: {admin_password}')
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@example.com', is_admin=True)
        admin.set_password(admin_password)
        admin.email_verified = True
        db.session.add(admin)

    db.session.commit()
    print('[entrypoint] Database initialized successfully')

    # Create MySQL exporter user for monitoring
    try:
        exporter_password = os.environ.get('MYSQL_EXPORTER_PASSWORD', 'exporter_password')
        conn = db.engine.raw_connection()
        cursor = conn.cursor()
        cursor.execute(\"\"\"
            CREATE USER IF NOT EXISTS 'exporter'@'%' IDENTIFIED BY %s
        \"\"\", (exporter_password,))
        cursor.execute(\"\"\"
            GRANT PROCESS, REPLICATION CLIENT, SELECT ON *.* TO 'exporter'@'%'
        \"\"\")
        cursor.execute('FLUSH PRIVILEGES')
        conn.commit()
        cursor.close()
        conn.close()
        print('[entrypoint] MySQL exporter user created')
    except Exception as e:
        print(f'[entrypoint] Exporter user setup skipped: {e}')
" || echo "[entrypoint] Database init failed or already initialized"

echo "[entrypoint] Starting gunicorn..."
exec "$@"
