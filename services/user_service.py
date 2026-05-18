from database.db import get_connection

import bcrypt


# =========================
# 注册
# =========================
def register():

    username = input("请输入用户名：")

    password = input("请输入密码：")

    # 密码加密
    hashed_password = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    conn = get_connection()

    cursor = conn.cursor()

    # 检查用户是否存在
    cursor.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    )

    user = cursor.fetchone()

    if user:

        print("用户名已存在")

        conn.close()

        return

    # 注册用户
    cursor.execute(
        "INSERT INTO users (username, password) VALUES (?, ?)",
        (username, hashed_password)
    )

    conn.commit()

    conn.close()

    print("注册成功")


# =========================
# 登录
# =========================
def login():

    username = input("请输入用户名：")

    password = input("请输入密码：")

    conn = get_connection()

    cursor = conn.cursor()

    # 查询用户
    cursor.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    )

    user = cursor.fetchone()

    conn.close()

    if user:

        stored_password = user[2].encode("utf-8")

        # 验证密码
        if bcrypt.checkpw(
            password.encode("utf-8"),
            stored_password
        ):

            print("登录成功")

            return user

    print("用户名或密码错误")

    return None