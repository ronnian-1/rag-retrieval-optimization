# 知识库信息数据库的路径
SQLALCHEMY_DATABASE = './db_server/data/'

# 知识库信息数据库的URI
SQLALCHEMY_DATABASE_URI = "sqlite:///./db_server/data/info.db"

# 存储向量数据库的路径
KB_DIR = "./knowledgebases"

# 存储的是上传知识库的文档
FILE_STORAGE_DIR = "./data"

embedding_model_path = './models/AI-ModelScope/bge-large-zh-v1__5'

# 大模型聊天中上传文件存储的路径
TEMP_FILE_STORAGE_DIR = './temp/data'

# chat_routes.py访问ChatOpenAI中使用
chat_model_name = "Qwen/Qwen2.5-72B-Instruct"
# chat_model_name =  "Pro/zai-org/GLM-4.7"
api_key = "sk-bbvwwuwtsfudwzgkmhfoqqxxybxoypejhpoquwsrtxtizips"
base_url = "https://api.siliconflow.cn/v1"

# 设置超时
TIME_OUT = 60

# 媒体文件保存路径，在tools/code_interpreter.py下使用
MEDIA_DIR = "./temp/medias"