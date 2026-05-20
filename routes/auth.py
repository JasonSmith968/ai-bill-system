from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    session,
    flash
)

import bcrypt

from database.db import get_connection


auth_bp = Blueprint(
    "auth",
    __name__
)


# =========================
# 登录
# =========================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]

        conn = get_connection()

        cursor = conn.cursor()

        # SQLite 使用 ?
        cursor.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )

        user = cursor.fetchone()

        cursor.close()

        conn.close()

        # 校验用户和密码
        if user and bcrypt.checkpw(
            password.encode("utf-8"),
            user["password"].encode("utf-8")
        ):

            session["user_id"] = user["id"]

            session["username"] = user["username"]

            return redirect("/dashboard")

        flash("用户名或密码错误")

    return render_template("login.html")


# =========================
# 注册
# =========================
@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        conn = get_connection()

        cursor = conn.cursor()

        # SQLite 使用 ?
        cursor.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            flash("用户名已存在")

            return redirect("/register")

        cursor.execute(
            """
            INSERT INTO users (username, password)
            VALUES (?, ?)
            """,
            (username, hashed_password)
        )

        conn.commit()

        cursor.close()

        conn.close()

        flash("注册成功")

        return redirect("/login")

    return render_template("register.html")


# =========================
# 退出登录
# =========================
@auth_bp.route("/logout")
def logout():

    session.clear()

    return redirect("/login")