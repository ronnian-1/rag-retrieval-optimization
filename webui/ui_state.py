import gradio as gr
import uuid
from webui.user_api import login

# 登录态/权限控制
def render_ui(auth):

    if not auth["login"]:
        return (
            gr.update(visible=False),
            gr.update(visible=False)
        )

    if auth["role"] == "admin":
        return (
            gr.update(visible=True),
            gr.update(visible=True)
        )

    return (
        gr.update(visible=True),
        gr.update(visible=False)
    )


# def login_ui(username):

#     msg, role = login(username)

#     auth = {
#         "login": True,
#         "role": role,
#         "session_id": str(uuid.uuid4())
#     }

#     return msg, auth

def login_ui(username):
    msg, role = login(username)

    auth = {
        "login": True,
        "role": role,
        "session_id": str(uuid.uuid4())
    }

    return msg, auth


# def logout_ui():

#     auth = {
#         "login": False,
#         "role": "",
#         "session_id": ""
#     }

#     return auth, "已退出登录"

def logout_ui():
    auth = {
        "login": False,
        "role": "",
        "session_id": ""
    }

    return auth, "已退出登录"
