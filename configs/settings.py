import os


def _load_dotenv(dotenv_path=".env"):
    if not os.path.exists(dotenv_path):
        return

    with open(dotenv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def _env(name, default=""):
    return os.getenv(name, default)


_load_dotenv()

# 知识库信息数据库的路径
SQLALCHEMY_DATABASE = _env("SQLALCHEMY_DATABASE", "./db_server/data/")

# 知识库信息数据库的URI
SQLALCHEMY_DATABASE_URI = _env("SQLALCHEMY_DATABASE_URI", "sqlite:///./db_server/data/info.db")

# 存储向量数据库的路径
KB_DIR = _env("KB_DIR", "./knowledgebases")

# 存储的是上传知识库的文档
FILE_STORAGE_DIR = _env("FILE_STORAGE_DIR", "./data")

embedding_model_path = _env("EMBEDDING_MODEL_PATH", "./models/AI-ModelScope/bge-large-zh-v1__5")
embedding_model_name = _env("EMBEDDING_MODEL_NAME", "BAAI/bge-large-zh-v1.5")

# 大模型聊天中上传文件存储的路径
TEMP_FILE_STORAGE_DIR = _env("TEMP_FILE_STORAGE_DIR", "./temp/data")

# chat_routes.py访问ChatOpenAI中使用
chat_model_name = _env("CHAT_MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
# chat_model_name =  "Pro/zai-org/GLM-4.7"
api_key = _env("SILICONFLOW_API_KEY", _env("OPENAI_API_KEY", ""))
base_url = _env("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
serpapi_api_key = _env("SERPAPI_API_KEY", "")
web_search_proxy = _env("WEB_SEARCH_PROXY", "http://api.wlai.vip")
CORS_ALLOW_ORIGINS = _env("CORS_ALLOW_ORIGINS", "*").split(",")

# 设置超时
TIME_OUT = int(_env("TIME_OUT", "60"))

# 媒体文件保存路径，在tools/code_interpreter.py下使用
MEDIA_DIR = _env("MEDIA_DIR", "./temp/medias")
