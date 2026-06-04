"""Subscription plan model."""

from datetime import datetime
from extensions import db


class Plan(db.Model):
    __tablename__ = 'plans'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # free, pro
    display_name = db.Column(db.String(100), nullable=False)  # 免费版, Pro版
    price_monthly = db.Column(db.Float, default=0)
    price_yearly = db.Column(db.Float, default=0)
    ai_calls_limit = db.Column(db.Integer, default=50)
    token_limit = db.Column(db.Integer, default=100000)
    features = db.Column(db.JSON, default=list)
    is_active = db.Column(db.Boolean, default=True)
    stripe_price_id_monthly = db.Column(db.String(200), nullable=True)
    stripe_price_id_yearly = db.Column(db.String(200), nullable=True)
    alipay_plan_id = db.Column(db.String(200), nullable=True)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subscriptions = db.relationship('Subscription', backref='plan', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'price_monthly': self.price_monthly,
            'price_yearly': self.price_yearly,
            'ai_calls_limit': self.ai_calls_limit,
            'token_limit': self.token_limit,
            'features': self.features or [],
            'sort_order': self.sort_order
        }


def seed_plans():
    """Seed default plans if they don't exist."""
    if Plan.query.count() == 0:
        free = Plan(
            name='free',
            display_name='免费版',
            price_monthly=0,
            price_yearly=0,
            ai_calls_limit=50,
            token_limit=100000,
            features=[
                '基础记账功能',
                'AI 智能记账 (50次/月)',
                'Dashboard 数据概览',
                '收支记录管理',
                '基础分类统计',
            ],
            sort_order=0
        )
        pro = Plan(
            name='pro',
            display_name='Pro 版',
            price_monthly=29,
            price_yearly=268,
            ai_calls_limit=500,
            token_limit=1000000,
            features=[
                '全部免费版功能',
                'AI 智能记账 (500次/月)',
                'AI 财务分析助手',
                'Multi-Agent 协作分析',
                '月度报告导出 (PDF/Excel)',
                '订阅与异常消费检测',
                '预算优化建议',
                '优先技术支持',
            ],
            sort_order=1
        )
        team = Plan(
            name='team',
            display_name='团队版',
            price_monthly=79,
            price_yearly=688,
            ai_calls_limit=2000,
            token_limit=5000000,
            features=[
                '全部 Pro 版功能',
                'AI 智能记账 (2000次/月)',
                '支持 5 个团队成员',
                '团队财务管理',
                '高级数据导出',
                '专属客户经理',
                'API 接口访问',
            ],
            sort_order=2
        )
        db.session.add_all([free, pro, team])
        db.session.commit()
