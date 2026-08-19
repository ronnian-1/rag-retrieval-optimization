import os

from fastapi import FastAPI #导入FastAPI框架
from fastapi.middleware.cors import CORSMiddleware #导入跨资源共享中间件，允许不同的客户端访问服务器 
from fastapi.staticfiles import StaticFiles
from chat.chat_routes import chat_router #导入聊天相关的路由对象
from knowledgebase_server.kb_routes import kbapp #导入定义了知识库相关的路由对象
from user_serve.user_routes import user_router
from configs.settings import CORS_ALLOW_ORIGINS, MEDIA_DIR

app = FastAPI()
# 允许跨域请求
app.add_middleware(  #添加中间件
    CORSMiddleware,  #指定添加的中间件是跨源资源共享中间件
    allow_origins=CORS_ALLOW_ORIGINS,  #允许配置的客户端访问服务器
    allow_credentials=True,  #允许客户端发送凭证（如：cookies
    allow_methods=["*"],   #允许所有HTTP方法（GET，POST，PUT，DELET
    allow_headers=["*"],   #允许所有自定义请求
)

os.makedirs(MEDIA_DIR, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

app.include_router(chat_router)
app.include_router(kbapp)
app.include_router(user_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=6605, log_level="info")