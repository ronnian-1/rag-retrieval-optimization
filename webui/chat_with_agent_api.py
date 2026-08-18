import requests
import json
import uuid


# # backend_url = "http://127.0.0.1:6605/chatbot/chat"
# chat_with_agent_url = "http://127.0.0.1:6605/chatbot/agent_chat"
# def chat_with_backend(prompt, history, sys_prompt, history_len, temperature, top_p, max_tokens, stream,session_id):

#     files=[('files',(open(file_path,"rb"))) for file_path in prompt["files"]]
#     print("-------------files:",files)
#     # query = ""
#     if prompt["files"]!=[]:
#         query = f'{prompt["text"]}\n' + "".join(prompt["files"][0])
#     else:
#         query = f'{prompt["text"]}\n'

#     # 构建请求数据
#     data = {
#         "query": query,
#         "sys_prompt": sys_prompt,
#         "history_len": history_len,
#         "history": [str(h) for h in history],
#         "temperature": temperature,
#         "top_p": top_p,
#         "max_tokens": max_tokens,        
#         "session_id":session_id
#     }
#     # 发送请求到 FastAPI 后端
#     try:
#         response = requests.post(chat_with_agent_url,files=files, data=data, stream=True)
#         if response.status_code == 200:
#             # 接收所有chunks的内容
#             chunks = ""
#             if stream:
#                 #chun_size=None 表示一次性读取完整块，decode_ubicode=True 表示对内容进行Unicode解码
#                 for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
#                     if chunk:
#                         data =json.loads(chunk)  #将内容块解析为JSON格式的数据
#                         chunks += data.get('answer','')
#                         yield chunks
#             else:
#                 for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
#                     data = json.loads(chunk)
#                     chunks += data.get('answer','')
#                 yield chunks

#         else:
#             yield "请求失败，请检查后台服务器是否正常运行"
#     except Exception as e:
#         yield f"发生错误：{e}"

chat_with_agent_url = "http://127.0.0.1:6605/chatbot/agent_chat"

def chat_with_backend(prompt, history, sys_prompt, history_len, temperature, top_p, max_tokens, stream, session_state):
    # ✅ 正确提取 session_id
    if isinstance(session_state, dict):
        session_id = session_state.get("session_id", str(uuid.uuid4()))
    else:
        session_id = str(uuid.uuid4())
    
    # ✅ 处理文件（修复空列表问题）
    files = []
    if prompt.get("files") and prompt["files"] != []:
        try:
            files = [('files', (open(file_path, "rb"))) for file_path in prompt["files"]]
            print("-------------files:", files)
        except Exception as e:
            print(f"文件打开失败: {e}")
    
    # 构建查询内容
    if prompt.get("files") and prompt["files"] != []:
        query = f'{prompt["text"]}\n' + "".join(prompt["files"][0])
    else:
        query = f'{prompt["text"]}\n'

    # 构建请求数据
    data = {
        "query": query,
        "sys_prompt": sys_prompt,
        "history_len": history_len,
        "history": [str(h) for h in history],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,        
        "session_id": session_id  # ✅ 现在传递的是字符串
    }
    
    # 发送请求到 FastAPI 后端
    try:
        response = requests.post(chat_with_agent_url, files=files, data=data, stream=True)
        if response.status_code == 200:
            chunks = ""
            if stream:
                for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                    if chunk:
                        data = json.loads(chunk)
                        chunks += data.get('answer','')
                        yield chunks
            else:
                for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                    data = json.loads(chunk)
                    chunks += data.get('answer','')
                yield chunks
        else:
            yield "请求失败，请检查后台服务器是否正常运行"
    except Exception as e:
        yield f"发生错误：{e}"

