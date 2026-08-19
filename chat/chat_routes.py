import json
import asyncio
import os
from ast import literal_eval
from tools.tools_select import tools
from typing import List,AsyncIterable
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import create_react_agent,AgentExecutor
from langchain.prompts  import SystemMessagePromptTemplate,HumanMessagePromptTemplate,AIMessagePromptTemplate
from configs.prompt import PROMPT_TEMPLATES
from configs.settings import chat_model_name,api_key,base_url,TIME_OUT,TEMP_FILE_STORAGE_DIR
from utils.callback import CustomAsyncIteratorCallbackHandler
from db_server.base import session
from db_server.knowledge_base_repository import list_kb_from_db
from tools.code_interpreter import code_interpreter
from utils.load_docs import get_file_content
from db_server.base import ChatHistory


from typing import List
from fastapi import FastAPI,Body,APIRouter,UploadFile,Form,HTTPException
# 同步
from openai import OpenAI
# 异步
from openai import AsyncOpenAI
# 流式响应
from fastapi.responses import StreamingResponse

# 初始化FastAPI应用
# app=FastAPI()

chat_router = APIRouter(prefix="/chatbot",  tags=["chatbot managerment"])

# api_key="<set via SILICONFLOW_API_KEY>"
# base_url="https://api.siliconflow.cn/v1"
# client=AsyncOpenAI(api_key=api_key,base_url=base_url)


def safe_upload_path(upload_dir, filename):
    safe_filename = os.path.basename(filename or "")
    if safe_filename in ("", ".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    upload_dir_abs = os.path.abspath(upload_dir)
    file_path = os.path.abspath(os.path.join(upload_dir_abs, safe_filename))
    if os.path.commonpath([upload_dir_abs, file_path]) != upload_dir_abs:
        raise HTTPException(status_code=400, detail="Invalid file path")

    return file_path
# 先将传入的文件存储对应用户下的目录
# 查找当前用户目录下的所有文件，读取内容并返回字符串，包括文件路径和内容
def files_rag(files,uuid):
    # 定义存储路径 TEMP_FILE_STORAGE_DIR = "./temp/data"
    kb_file_storage_path = os.path.join(TEMP_FILE_STORAGE_DIR,uuid)
    result = []
    # 确保存储目录存在
    os.makedirs(kb_file_storage_path,exist_ok=True)
    if files:
        for file in files:
            # 保存文件到指定路径
            file_path = safe_upload_path(kb_file_storage_path,file.filename)

            with open(file_path,"wb") as f:
                f.write(file.file.read())

    # 遍历目录中的所有文件并读取内容
    for filename in os.listdir(kb_file_storage_path):
        file_path = os.path.join(kb_file_storage_path,filename)
        if os.path.isfile(file_path):
            file_content = get_file_content(file_path)

            # 直接将路径和内容拼接到结果字符串
            result.append(f"document:.{file_path}\ncontent:{file_content}\n")
    return "".join(result)


@chat_router.post("/agent_chat")
async def agent_chat(
    files: List[UploadFile] = None,
    query: str = Form(...,description="用户输入"),
    sys_prompt: str =  Form("You are a helpful assistant.",description="系统提示"),
    history_len: int = Form(-1,description="保留历史消息的数量"),
    history: List[str] = Form([],description="历史对话"),
    temperature: float = Form(0.5,description="LLM采样温度"),
    max_tokens: int = Form(1024,description="LLM最大token数配置"),
    session_id: str=Form(None,description="会话表示")
):
    documents = files_rag(files,session_id)
    # 将字符串形式的Python数据结构安全转换为实际的python数据类型
    history =[literal_eval(item) for item in history]
    # 控制历史记录长度，保留指定数量的消息
    histories = ""
    if history_len > 0 :
        history = history[-2 *history_len:]

    # 在消息列表中加入历史消息
    for msg in history:
        role = msg.get("role")
        content = msg.get("content")
        histories += f"{role}:{content}\n\n"

    async def agent_chat_iterator() -> AsyncIterable[str]:
        # 使用自己定义的回调处理函数
        callback = CustomAsyncIteratorCallbackHandler()
        callbacks = [callback]

        # 定义聊天模型
        chat_model=ChatOpenAI(
            model=chat_model_name,
            api_key = api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=True,
            callbacks=callbacks
        )

        # 定义系统提示，用于设置行为规则
        system_prompt = SystemMessagePromptTemplate.from_template(
            sys_prompt
        )

        human_prompt = HumanMessagePromptTemplate.from_template(
            PROMPT_TEMPLATES["agent"]
        )

        chat_prompt = ChatPromptTemplate.from_messages([system_prompt,human_prompt])

        # 创建代理
        agent = create_react_agent(chat_model,tools,chat_prompt,stop_sequence=['\nObserv'])
        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True
        )

        # 列出所有知识库
        knowledgebases = list_kb_from_db(session)
        # 整理成字符串
        kbs = "".join([f"{kb['kb_name']} - {kb['kb_info']} \n" for kb in knowledgebases])
        code_interpreter.output_files,code_interpreter.output_codes = "",""
        # 开启异步执行agent
        # save_chat(username, "user", query)
        task = asyncio.create_task(
            agent_executor.acall(
                inputs={"input":query,"history":histories,"knowledgebases":kbs,"documents":documents})
        )

        # 流式输出
        async for token in callback.aiter():
            response_date={
                "answer":token,
            }
            yield json.dumps(response_date).encode('utf-8')

        await asyncio.wait_for(task,TIME_OUT)

        output_files,output_codes=code_interpreter.get_outputs()
        if output_files:
                yield json.dumps({"answer":f'\n\n{output_codes}\n\n![](http://localhost:6605{output_files})'}).encode('utf-8')
        else:
            yield json.dumps({"answer":f'\n\n{output_codes}'}).encode('utf-8')

    return StreamingResponse(agent_chat_iterator(),media_type="application/json")



# @chat_router.post("/agent_chat")
# async def agent_chat(
#     files: List[UploadFile] = None,
#     query: str = Form(...,description="用户输入"),
#     sys_prompt: str = Form("You are a helpful assistant.",description="系统提示"),
#     history_len: int = Form(-1,description="保留历史消息的数量"),
#     history: List[str] = Form([],description="历史对话"),
#     temperature: float = Form(0.5,description="LLM采样温度"),
#     max_tokens: int = Form(1024,description="LLM最大token数配置"),
#     session_id: str = Form(None,description="会话表示"),
#     username: str = Form(None,description="用户名")
# ):

# # 初始化历史对话列表
# messages=[]

# # 定义路由，实现接口对接
# # Body从请求体中提取数据
# @chat_router.post("/chat")
# async def chat(
#     query:str =Body(...,description="用户输入"),
#     # ...代表必须输入
#     sys_prompt:str=Body("You are a helpful assistant",description="系统提示"),
#     history_len:int=Body(-1,description="保留历史消息的数量"),
#     history:List =Body([],description="历史对话"),
#     temperature:float=Body(0.7,description="LLM采样温度"),
#     top_p:float=Body(0.7,description="LLM采样概率"),
#     max_tokens:int=Body(100,description="LLM最大token数配置"),
# ):
#     global messages

#     # 控制历史记录长度，指定指定数量的信息，每轮都有用户和助手两个，所以乘以-2
#     # 如果为-1就不进入if，则保留所有历史信息，不进行截取
#     if history_len>0:
#         history=history[-2*history_len:]

#     # 在消息列表中加入系统提示
#     messages.clear()
#     messages.append({"role":"system","content":sys_prompt})

#     # 在消息列表中加入历史信息
#     messages.extend(history)

#     # 在消息列表中加入用户输入
#     messages.append({"role":"user","content":query})
#     print(messages)

#     # 生成异步生成器，用于流式输出助手响应
#     async def generate_response():
#         # 发送请求
#         response =await client.chat.completions.create(
#             #model="Pro/zai-org/GLM-4.7",
#             model=chat_model_name,
#             messages=messages,
#             max_tokens=max_tokens,
#             temperature=temperature,
#             top_p=top_p,
#             stream=True,#启动流式响应
#         )


#         # 逐步获取助手的响应内容并流式返回
#         async for chunk in response:
#             chunk_message=chunk.choices[0].delta.content
#             if chunk_message:
#                 # 函数中看到 yield 关键字时，这意味着该函数是一个生成器函数。
#                 # 如果存在有效消息chunk_message，则使用 yield 将这条消息返回给调用者。
#                 yield chunk_message


#     # 返回 StreamingResponse，以流的形式发送数据。流式响应fastapi的客户端
#     return StreamingResponse(generate_response(),media_type="text/plain")

# # if __name__=="__main__":
# #     import uvicorn
# #     # 启动服务器
# #     uvicorn.run("d10_FastAPI_for_vllm:app",host="127.0.0.1",port=6605,log_level="info",reload=True)



