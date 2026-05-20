from routes.export import export_bp
from flask import (
    Flask,
    render_template,
    redirect,
    session
)
from database.db import (
    init_db,
    get_connection
)

import bcrypt
import json

app = Flask(__name__)

from routes.auth import auth_bp
from routes.bill import bill_bp
from routes.dashboard import dashboard_bp

app.register_blueprint(auth_bp)
app.register_blueprint(bill_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(export_bp)

@app.route("/")
def index():
    # 已登录直接进dashboard
    if "user_id" in session:
        return redirect("/dashboard")

    return render_template("index.html")
app.secret_key = "ai_bill_secret"
# 初始化数据库
init_db()




# 404 页面
@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "404.html"
    ), 404


# 500 页面
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
