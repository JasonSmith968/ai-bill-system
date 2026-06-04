from flask import (
    Flask,
    render_template,
    redirect,
    session,
    request
)
from flask_cors import CORS
from database.db import (
    init_db,
    get_connection
)
from routes.api import api_bp
from models import db

from routes.auth import auth_bp
from routes.bill import bill_bp
from routes.dashboard import dashboard_bp
from routes.export import export_bp

import bcrypt
import json

# =========================
# 创建 Flask
# =========================
app = Flask(__name__)

CORS(app)
app.secret_key = "ai_bill_secret"

app.register_blueprint(api_bp)
# =========================
# SQLAlchemy 配置
# =========================
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ai_account.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# 初始化 ORM
db.init_app(app)

# =========================
# 初始化旧数据库
# =========================
init_db()

# =========================
# 创建 ORM 数据表
# =========================
with app.app_context():

    db.create_all()

# =========================
# 注册蓝图
# =========================
app.register_blueprint(auth_bp)

app.register_blueprint(bill_bp)

app.register_blueprint(dashboard_bp)

app.register_blueprint(export_bp)

# =========================
# 首页
# =========================
@app.route("/")
def index():

    # 已登录直接进入 dashboard
    if "user_id" in session:

        return redirect("/dashboard")

    return render_template("index.html")

# =========================
# AI 自动记账
# =========================
@app.route("/ai_add", methods=["GET", "POST"])
def ai_add():

    if "user_id" not in session:

        return redirect("/login")

    if request.method == "POST":

        bill_text = request.form["bill_text"]

        print(bill_text)

    return render_template("ai_add.html")

# =========================
# 404 页面
# =========================
@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "404.html"
    ), 404

# =========================
# 500 页面
# =========================
@app.errorhandler(500)
def internal_server_error(error):

    return render_template(
        "500.html"
    ), 500

# =========================
# 启动
# =========================
if __name__ == "__main__":

    app.run(debug=True)