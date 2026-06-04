"""数据库初始化脚本"""
import os
import secrets
import string
from app import create_app
from extensions import db
from models.user import User
from models.transaction import Category
import models  # noqa: F401 - registers all models


def init_database():
    """初始化数据库"""
    app = create_app()

    with app.app_context():
        # 创建所有表
        db.create_all()

        # 创建默认分类
        default_categories = [
            # 支出分类
            {'name': '餐饮', 'type': 'expense', 'icon': 'utensils', 'color': '#EF4444'},
            {'name': '交通', 'type': 'expense', 'icon': 'car', 'color': '#F59E0B'},
            {'name': '购物', 'type': 'expense', 'icon': 'shopping-bag', 'color': '#8B5CF6'},
            {'name': '娱乐', 'type': 'expense', 'icon': 'gamepad', 'color': '#EC4899'},
            {'name': '住房', 'type': 'expense', 'icon': 'home', 'color': '#3B82F6'},
            {'name': '医疗', 'type': 'expense', 'icon': 'hospital', 'color': '#10B981'},
            {'name': '教育', 'type': 'expense', 'icon': 'book', 'color': '#6366F1'},
            {'name': '通讯', 'type': 'expense', 'icon': 'phone', 'color': '#14B8A6'},
            {'name': '其他', 'type': 'expense', 'icon': 'tag', 'color': '#6B7280'},
            # 收入分类
            {'name': '工资', 'type': 'income', 'icon': 'money-bill', 'color': '#22C55E'},
            {'name': '奖金', 'type': 'income', 'icon': 'gift', 'color': '#F59E0B'},
            {'name': '投资', 'type': 'income', 'icon': 'chart-line', 'color': '#3B82F6'},
            {'name': '兼职', 'type': 'income', 'icon': 'briefcase', 'color': '#8B5CF6'},
            {'name': '红包', 'type': 'income', 'icon': 'envelope', 'color': '#EF4444'},
            {'name': '其他', 'type': 'income', 'icon': 'tag', 'color': '#6B7280'},
        ]

        for cat_data in default_categories:
            existing = Category.query.filter_by(
                name=cat_data['name'],
                type=cat_data['type']
            ).first()

            if not existing:
                category = Category(
                    name=cat_data['name'],
                    type=cat_data['type'],
                    icon=cat_data['icon'],
                    color=cat_data['color'],
                    is_default=True
                )
                db.session.add(category)

        # 创建管理员账号 — 密码从环境变量读取，未设置时自动生成
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin_password = os.environ.get('ADMIN_PASSWORD')
            if not admin_password:
                admin_password = ''.join(secrets.choice(
                    string.ascii_letters + string.digits + '!@#$%^&*'
                ) for _ in range(16))
                print(f"[WARNING] ADMIN_PASSWORD not set. Generated random password: {admin_password}")
                print(f"[WARNING] Save this password immediately — it will not be shown again.")

            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin.set_password(admin_password)
            admin.email_verified = True
            db.session.add(admin)
            db.session.flush()

            # Create default tenant for admin
            from services.tenant_service import create_tenant
            tenant, _ = create_tenant('Admin的工作区', admin.id)
            if tenant:
                admin.tenant_id = tenant.id

        db.session.commit()
        print("数据库初始化完成！")


if __name__ == '__main__':
    init_database()