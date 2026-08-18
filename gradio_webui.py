# import gradio as gr
# import requests
# # from UserUI import create_user, delete_user, list_users
# from webui.knowledgebase_api import create_kb,delete_kb,list_kb,update,upload_docs
# # from stu_ui import create_stu,delete_stu,list_stu
# from webui.chat_with_agent_api import chat_with_backend
# import uuid

# # 在Gradio应用加载时生成新的会话id
# def on_app_load():
#     session_id = str(uuid.uuid4())
#     return session_id

# # 使用gradio.Blocks创建一个块，并设置可以填充高度和宽度
# with gr.Blocks(fill_width=True, fill_height=True) as demo:
#     # 创建session_id会有独立的不重复32位编码来给每个对话命名temp/data下的文件，不同的用户产生独立的gr.State实例，数据不会再不同用户之间共享
#     session_state = gr.State(value=on_app_load)
#     print("session_state===============",session_state)

#     # 创建一个标签页
#     with gr.Tab(" 🤖 聊天机器人"):
#         # 添加标题
#         gr.Markdown("## 🩱🩳 关于泳装的智能回复机器人")

#         # 创建一个行布局
#         with gr.Row():
#             # 创建一个左侧的列布局
#             with gr.Column(scale=1, variant="panel") as sidebar_left:
#                 sys_prompt = gr.Textbox(label="系统提示词", value="You are a helpful assistant.Answer questions in Chinese!")
#                 history_len = gr.Slider(minimum=1, maximum=10, value=1, label="保留历史消息的数量")
#                 temperature = gr.Slider(minimum=0.01, maximum=2.0, value=0.5, step=0.01, label="temperature")
#                 top_p = gr.Slider(minimum=0.01, maximum=1.0, value=0.5, step=0.01, label="top_p")
#                 max_tokens = gr.Slider(minimum=64, maximum=512, value=512, step=8, label="max_tokens")
#                 stream = gr.Checkbox(label="stream", value=True)
#             # 创建右侧的列布局，设置比例为10
#             with gr.Column(scale=10) as main:
#                 # 创建聊天机器人的聊天界面，高度为500px
#                 chatbot = gr.Chatbot(type="messages", height=600)
#                 # 创建chatinterface，用于处理聊天的逻辑.fn中设置的是和fastapi交互的函数
#                 iface = gr.ChatInterface(fn=chat_with_backend,
#                                 multimodal=True, #默认是False，只能输入文本，True表示这个聊天界面支持多模态交互，可以上传图片、音频等与聊天机器人交流
#                                 type="messages",
#                                 chatbot=chatbot,
#                                 additional_inputs=[
#                                     sys_prompt,
#                                     history_len,
#                                     temperature,
#                                     top_p,
#                                     max_tokens,
#                                     stream,
#                                     session_state  #使用session_state组件来传递会话ID
#                                 ])        



#     with gr.Tab("知识库管理"):
#         gr.Markdown("## 😸 知识库管理")
#         with gr.Row():
#             kb_name = gr.Textbox(label="知识库名称", placeholder="请输入知识库名称")
#         with gr.Row():
#             kb_info = gr.Textbox(label="知识库描述", placeholder="请输入知识库描述")
#         with gr.Row():
#             # 隐藏的消息框，用于显示操作结果
#             messdescription_box = gr.Markdown(visible=False)
#         with gr.Row():
#             create_button = gr.Button("创建知识库")
#             delete_button = gr.Button("删除知识库")

#         with gr.Row():
#             name_select = gr.Dropdown(label="选择知识库", choices=[], interactive=True,allow_custom_value=False) 

#         demo.load(
#             fn=list_kb,
#             outputs=name_select,
#             queue=True  # 确保在界面渲染完成后执行
#         )


#         # 选择文件那一块
#         # with gr.Row():
#         #     kb_name_upload=gr.Dropdown(label="选择知识库",choices=[])
#         with gr.Row():
#             file_uploaded = gr.Files(label="已选择的文件",visible=False)
#         with gr.Row():
#             file_upload=gr.Files(label="选择文件")
#         with gr.Row():
#             chunk_size=gr.Number(label="知识库中单段文本最大长度(chunk_size)",value=128,minimum=1,maximum=800)
#             chunk_overlap=gr.Number(label="知识库中相邻文本重合长度(chunk_overlap)",value=20,minimum=0,maximum=400)
#         with gr.Row():
#             upload_button=gr.Button("上传并向量化")
#         with gr.Row():
#             # 隐藏的消息框，用于显示操作结果
#             upload_message_box=gr.Markdown(visible=False)


#         create_button.click(create_kb,[kb_name,kb_info],[messdescription_box,kb_name,kb_info]).then(fn=list_kb,outputs=name_select)
#         delete_button.click(delete_kb,# 删除函数
#                             inputs=[name_select], # 下拉框选中项
#                             outputs=[messdescription_box] # 显示删除成功/失败信息
#                             ).then(fn=list_kb,inputs=[],outputs=[name_select]) # 刷新下拉框列表
                                


#         file_upload.upload(fn=update,inputs=[file_upload],outputs=[file_uploaded,file_upload])
#         upload_button.click(upload_docs,[name_select,file_uploaded,chunk_size,chunk_overlap],[upload_message_box,file_uploaded])


# # demo启动，点击运行就可以看到
# demo.launch()








import gradio as gr
import requests
# from UserUI import create_user, delete_user, list_users
from webui.knowledgebase_api import create_kb,delete_kb,list_kb,update,upload_docs
# from stu_ui import create_stu,delete_stu,list_stu
from webui.chat_with_agent_api import chat_with_backend
import uuid
from webui.user_api import login
from webui.ui_state import render_ui, login_ui,logout_ui
# from webui.chat_ui import chat_ui

# def show_tabs(role, auth):
#     if not auth:
#         return gr.update(visible=False), gr.update(visible=False)

#     if role == "admin":
#         return gr.update(visible=True), gr.update(visible=True)

#     return gr.update(visible=True), gr.update(visible=False)



# 在Gradio应用加载时生成新的会话id
def on_app_load():
    session_id = str(uuid.uuid4())
    return session_id

# def login_ui(username):
#     msg, role = login(username)

#     if role in ["admin", "user"]:
#         return msg, role, True

#     return msg, role, False



# 使用gradio.Blocks创建一个块，并设置可以填充高度和宽度
with gr.Blocks(fill_width=True, fill_height=True) as demo:
    # 创建session_id会有独立的不重复32位编码来给每个对话命名temp/data下的文件，不同的用户产生独立的gr.State实例，数据不会再不同用户之间共享
    session_state = gr.State({
    "session_id": str(uuid.uuid4()),
    "history": []})
    # role_state = gr.State(value="")
    auth_state = gr.State({
    "login": False,
    "role": str,
    "session_id": str})
    print("session_state===============",session_state)


    
    with gr.Tab(" 🤖 聊天机器人", visible=False) as chat_tab:
        # 添加标题
        gr.Markdown("## 🩱🩳 关于泳装的智能回复机器人")

        # 创建一个行布局
        with gr.Row():
            # 创建一个左侧的列布局
            with gr.Column(scale=1, variant="panel") as sidebar_left:
                sys_prompt = gr.Textbox(label="系统提示词", value="You are a helpful assistant.Answer questions in Chinese!")
                history_len = gr.Slider(minimum=1, maximum=10, value=1, label="保留历史消息的数量")
                temperature = gr.Slider(minimum=0.01, maximum=2.0, value=0.5, step=0.01, label="temperature")
                top_p = gr.Slider(minimum=0.01, maximum=1.0, value=0.5, step=0.01, label="top_p")
                max_tokens = gr.Slider(minimum=64, maximum=512, value=512, step=8, label="max_tokens")
                stream = gr.Checkbox(label="stream", value=True)
            # 创建右侧的列布局，设置比例为10
            with gr.Column(scale=10) as main:
                # 创建聊天机器人的聊天界面，高度为500px
                chatbot = gr.Chatbot(type="messages", height=600)
                # 创建chatinterface，用于处理聊天的逻辑.fn中设置的是和fastapi交互的函数
                iface = gr.ChatInterface(fn=chat_with_backend,
                                multimodal=True, #默认是False，只能输入文本，True表示这个聊天界面支持多模态交互，可以上传图片、音频等与聊天机器人交流
                                type="messages",
                                chatbot=chatbot,
                                additional_inputs=[
                                    sys_prompt,
                                    history_len,
                                    temperature,
                                    top_p,
                                    max_tokens,
                                    stream,
                                    session_state  #使用session_state组件来传递会话ID
                                ])        




    with gr.Tab("知识库管理", visible=False) as kb_tab:
        gr.Markdown("## 😸 知识库管理")
        with gr.Row():
            kb_name = gr.Textbox(label="知识库名称", placeholder="请输入知识库名称")
        with gr.Row():
            kb_info = gr.Textbox(label="知识库描述", placeholder="请输入知识库描述")
        with gr.Row():
            # 隐藏的消息框，用于显示操作结果
            messdescription_box = gr.Markdown(visible=False)
        with gr.Row():
            create_button = gr.Button("创建知识库")
            delete_button = gr.Button("删除知识库")

        with gr.Row():
            name_select = gr.Dropdown(label="选择知识库", choices=[], interactive=True,allow_custom_value=False) 

        demo.load(
            fn=list_kb,
            outputs=name_select,
            queue=True  # 确保在界面渲染完成后执行
        )


        # 选择文件那一块
        # with gr.Row():
        #     kb_name_upload=gr.Dropdown(label="选择知识库",choices=[])
        with gr.Row():
            file_uploaded = gr.Files(label="已选择的文件",visible=False)
        with gr.Row():
            file_upload=gr.Files(label="选择文件")
        with gr.Row():
            chunk_size=gr.Number(label="知识库中单段文本最大长度(chunk_size)",value=128,minimum=1,maximum=800)
            chunk_overlap=gr.Number(label="知识库中相邻文本重合长度(chunk_overlap)",value=20,minimum=0,maximum=400)
        with gr.Row():
            upload_button=gr.Button("上传并向量化")
        with gr.Row():
            # 隐藏的消息框，用于显示操作结果
            upload_message_box=gr.Markdown(visible=False)


        create_button.click(create_kb,[kb_name,kb_info],[messdescription_box,kb_name,kb_info]).then(fn=list_kb,outputs=name_select)
        delete_button.click(delete_kb,# 删除函数
                            inputs=[name_select], # 下拉框选中项
                            outputs=[messdescription_box] # 显示删除成功/失败信息
                            ).then(fn=list_kb,inputs=[],outputs=[name_select]) # 刷新下拉框列表
                                


        file_upload.upload(fn=update,inputs=[file_upload],outputs=[file_uploaded,file_upload])
        upload_button.click(upload_docs,[name_select,file_uploaded,chunk_size,chunk_overlap],[upload_message_box,file_uploaded])


    with gr.Tab("用户登录"):
            gr.Markdown("## 用户登录")

            username_input = gr.Textbox(label="用户名")
            login_btn = gr.Button("登录")
            logout_btn = gr.Button("退出登录")

            login_msg = gr.Markdown()
            # 登录
            login_btn.click(
                fn=login_ui,
                inputs=[username_input],
                outputs=[login_msg, auth_state]
            ).then(
                fn=render_ui,
                inputs=[auth_state],
                outputs=[chat_tab, kb_tab]
            )

            # 退出登录（就在这里！！）
            logout_btn.click(
                fn=logout_ui,
                outputs=[auth_state, login_msg]
            ).then(
                fn=render_ui,
                inputs=[auth_state],
                outputs=[chat_tab, kb_tab]
            )


   

    


    

# demo启动，点击运行就可以看到
demo.launch()