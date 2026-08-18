import uuid
from db_server.user_repository import login_user

# 用户接口

# def login(username):

#     if not username.strip():
#         return None, "用户名不能为空"

#     session_id = login_user(username)

#     return session_id, f"登录成功，欢迎 {username}"

import requests

login_url = "http://127.0.0.1:6605/user/login"

def login(username):
    try:
        res = requests.post(
            login_url,
            json={"username": username}
        )

        data = res.json()

        # ❗防止后端异常返回
        if "message" not in data or "role" not in data:
            return "登录失败（后端返回异常）", "user"

        return data.get("message", "ok"), data.get("role", "user")

    except Exception as e:
        return f"请求失败: {str(e)}", "user"