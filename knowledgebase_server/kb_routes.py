# Description: 知识库管理API，使用硅基流动Embedding模型和本地FAISS向量存储库进行知识库的创建、删除、文件上传、文件删除、搜索等操作。
from fastapi import  Body,  APIRouter, Depends
# from UserBase import session
# from UserDB import add_user_to_db, del_user_from_db, list_user_from_db
from db_server.base import get_db
from db_server.knowledge_base_repository import add_kb_to_db,del_kb_from_db,list_kb_from_db
import shutil
from typing import List
from sqlalchemy.orm import Session

import jieba
from langchain_openai import OpenAIEmbeddings
from langchain.embeddings.base import Embeddings
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

from .loader.loader import data_loader
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from fastapi import HTTPException,APIRouter,Body,UploadFile,File,Form
from db_server.knowledge_base_repository import add_kb_to_db,del_kb_from_db
from configs.settings import KB_DIR,FILE_STORAGE_DIR,embedding_model_path,api_key,base_url,embedding_model_name
import os
import time

from langchain_community.document_loaders import TextLoader

# app = FastAPI()

kbapp = APIRouter(prefix="/kbs",  tags=["kbs managerment"])

# 确保知识库目录存在.KB_DIR="./knowledgebases"
if not os.path.exists(KB_DIR):
    os.makedirs(KB_DIR)



def safe_kb_name(kb_name):
    safe_name = (kb_name or "").strip()
    if safe_name in ("", ".", ".."):
        raise HTTPException(status_code=400, detail="Invalid knowledge base name")
    if os.path.basename(safe_name) != safe_name:
        raise HTTPException(status_code=400, detail="Invalid knowledge base name")
    return safe_name


def safe_kb_path(kb_name):
    safe_name = safe_kb_name(kb_name)
    kb_dir_abs = os.path.abspath(KB_DIR)
    kb_path = os.path.abspath(os.path.join(kb_dir_abs, f"{safe_name}.faiss"))
    if os.path.commonpath([kb_dir_abs, kb_path]) != kb_dir_abs:
        raise HTTPException(status_code=400, detail="Invalid knowledge base name")
    return kb_path


def safe_file_storage_path(kb_name):
    safe_name = safe_kb_name(kb_name)
    storage_dir_abs = os.path.abspath(FILE_STORAGE_DIR)
    storage_path = os.path.abspath(os.path.join(storage_dir_abs, safe_name))
    if os.path.commonpath([storage_dir_abs, storage_path]) != storage_dir_abs:
        raise HTTPException(status_code=400, detail="Invalid knowledge base name")
    return storage_path
def safe_upload_path(upload_dir, filename):
    safe_filename = os.path.basename(filename or "")
    if safe_filename in ("", ".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    upload_dir_abs = os.path.abspath(upload_dir)
    file_path = os.path.abspath(os.path.join(upload_dir_abs, safe_filename))
    if os.path.commonpath([upload_dir_abs, file_path]) != upload_dir_abs:
        raise HTTPException(status_code=400, detail="Invalid file path")

    return file_path, safe_filename
# 创建一个嵌入对象，父类是Embeddings，重写父类两个方法embed_documents和embed_query
class CustomEmbeddingModel(Embeddings):
    def __init__(self,model,model_name):
        self.model=model
        self.model_name=model_name
    # 用于将多个文本嵌入为向量
    def embed_documents(self, texts):
        return [self.model.client.create(model=self.model_name,input=text).data[0].embedding for text in texts]
    # 用于将单个查询文件文本嵌入为向量
    def embed_query(self, text):
        return self.model.client.create(model=self.model_name,input=text).data[0].embedding

_embedding_model = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        # openaiembedding类来创建一个嵌入模型实例，用于将文本嵌入为向量
        # 创建的embedding对象可以用于将文本转换为向量表示。这些向量捕捉了文本的语义信息，可以用于计算文本之间的相似度，构建语义搜索系统等
        embedding = OpenAIEmbeddings(
            api_key=api_key,
            base_url=base_url
        )
        # “BAAI/bge-large-zh-v1.5”模型名称，专门针对中文文本的嵌入任务
        # 创建CustomEmbeddingModel的实例，结合了OpenAi的嵌入模型实例与特定的中文嵌入模型bge
        # 创建的embedding_model实例可以用于将文本转换为向量表示
        _embedding_model = CustomEmbeddingModel(embedding,embedding_model_name)
    return _embedding_model
# 方式二:需要限制性utils/downloader.py将词嵌入模型存储到本地
# embedding_model=HuggingFaceBgeEmbeddings(model_name=embedding_model_path)


# 创建知识库的API
@kbapp.post("/create_kb")
async def create_kb(
        kb_name: str = Body(..., description="知识库名称"),  # Body是FastAPI 中的一个函数，用于从请求体中获取数据。... 表示这个参数是必需的
        kb_info: str = Body(..., description="知识库描述"),  # 函数的默认值是空字符串 ""，description: 提供参数的描述信息，用于生成 API 文档。
        db: Session = Depends(get_db),
):
    # msg = add_kb_to_db(session, kb_name, kb_info)
    kb_path = safe_kb_path(kb_name)

    # 检查知识库是否存在
    if os.path.exists(kb_path):
        raise HTTPException(status_code=400,detail="知识库已存在")
    
    # 卸磨杀驴环节
    # 创建一个Document对象，初始化文档正文内容和元数据。page_content被设置为"init"，metadate被设置为空字典
    doc=Document(page_content="init",metadata={})
    embedding_model = get_embedding_model()
    vector_store=FAISS.from_documents([doc],embedding_model,normalize_L2=True)
    """使用doc对应的初始文档创建了一个向量存储vector_store,用于为向量存储设置正确的维度与格式"""
    # 获取向量存储中所有文档的ID，并将其存储在列表ids中
    ids=list(vector_store.docstore._dict.keys())
    # 从向量存储中删除所有指定的ID文档
    vector_store.delete(ids)
    """这些操作确保向量存储在保存前是空的且包含必要的结构"""
    
    # 保存空的知识库，将向量存储保存到本地文件系统
    vector_store.save_local(kb_path)

    add_kb_to_db(db,kb_name,kb_info)
    return {"message":f"知识库‘{kb_name}'创建成功！"}


# 删除知识库API
@kbapp.delete("/delete_kb")
async def delete_kb(kb_name: str, db: Session = Depends(get_db)):
    kb_path=safe_kb_path(kb_name)   #KB_DIR="./knowledgebases"
    kb_files_path=safe_file_storage_path(kb_name)   #FILE_STORAGE_DIR="./data"
    
    # 判断知识库是否存在
    if not os.path.exists(kb_path):
        raise HTTPException(status_code=404,detail="Database not found")

    
    #删除向量数据库
    shutil.rmtree(kb_path)
    # 删除知识库关联文件
    if os.path.exists(kb_files_path):
        shutil.rmtree(kb_files_path)

    del_kb_from_db(db, kb_name)
    
    # return msg
    return {"message":f"Database'{kb_name}' deleted successfully"}

@kbapp.post("/upload_docs")
async def upload_docs(
    files:List[UploadFile]=File(...),
    kb_name:str=Form(...,description="知识库名称"),
    chunk_size:int=Form(128,description="知识库中单段文本最大长度"),
    chunk_overlap:int=Form(20,description="知识库中相邻文本重合长度"),
):
    kb_path=safe_kb_path(kb_name)   #KB_DIR="./knowledgebases"
    kb_file_storage_path = safe_file_storage_path(kb_name)  #FILE_STORAGE_DIR="./data"
    if not os.path.exists(kb_path):
        raise HTTPException(status_code=404,detail="Database not found")
    
    # 检查知识库对应的文件存储文件夹是否存储在，不存在则创建
    os.makedirs(kb_file_storage_path,exist_ok=True)
    updated_file=[]
    for file in files:
        # 将文件保存到对应知识库的文件夹中
        file_path,safe_filename=safe_upload_path(kb_file_storage_path,file.filename)
        file_content=file.file.read()

        with open(file_path,"wb") as f:
            f.write(file_content)  #将内容写进去
        
        # 解析文本文件内容并分割成小块
        # loader=data_loader().get_loader(file_path)
        loader=data_loader().get_loader(file_path)
        # 将文档加载为一个文档对象列表
        docs = loader.load()

        # 将文本递归分割成制定大小块的工具，通常用于NLP任务中，以便将长文本分割成适合模型处理的小块
        text_splitter=RecursiveCharacterTextSplitter(chunk_size=chunk_size,chunk_overlap=chunk_overlap,separators=[
            "\n\n",
            "\n",
            " ",
            ".",
            ",",
            "，",
            "。",
            ""
        ])

        # 将文档分割成多块
        chunks=text_splitter.split_documents(docs)
        for idx, chunk in enumerate(chunks):
            chunk.metadata.update({
                "kb_name": kb_name,
                "filename": safe_filename,
                "chunk_id": idx
            })

        # 加载知识库。load_local加载本地保存到向量数据库
        # embedding_model是一个嵌入模型（Embedding Model），将文本转换为向量
        # alow_dangerous_deserialization用于是否允许反序列化，有安全风险
        embedding_model = get_embedding_model()
        
        vectorstore=FAISS.load_local(kb_path,embedding_model,allow_dangerous_deserialization=True)

        # 将文件内容向量化并添加到知识库
        vectorstore.add_documents(chunks)
        # 保存更新后的知识库
        vectorstore.save_local(kb_path)
        updated_file.append(safe_filename)
    return {"message":f"File'{updated_file}' added to database '{kb_name}' successfully"}

# 在tools/knowledge_search.py文件中调用
@kbapp.post("/search_kb")
async def search_kb(
    kb_name: str = Body(...,description="知识库名称"),
    query: str = Body(...,description="问题")
):
    kb_path = safe_kb_path(kb_name)

    if not os.path.exists(kb_path):
        raise HTTPException(status_code=404,detail="Database not found")

    embedding_model = get_embedding_model()

    # 加载知识库，允许磁盘反序列化向量的危险操作
    faiss_load_start = time.time()
    vector_store = FAISS.load_local(kb_path,embedding_model,allow_dangerous_deserialization=True)
    faiss_load_elapsed = time.time() - faiss_load_start
    # 基于加载到向量存储库创建一个FAISS检索器，检索式返回最近的2
    faiss_retriever = vector_store.as_retriever(search_kwargs={"k":4})
    # 从向量存储库中的文档存储中获取所有文档
    docstore_start = time.time()
    docs=list(vector_store.docstore._dict.values())
    docstore_elapsed = time.time() - docstore_start
    doc_count = len(docs)
    # 基于文档创建一个BM25检索器
    bm25_start = time.time()
    bm25_retriever = BM25Retriever.from_documents(
        docs,
        preprocess_func=jieba.lcut_for_search)
    bm25_elapsed = time.time() - bm25_start
    bm25_retriever.k = 4 #设置BM25检索器返回的文档数量
    # 创建一个继承检索器，结合BM25和FAISS检索器的结果
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever,faiss_retriever],weights=[0.5,0.5]
    )
    # 使用继承检索其执行岔村获取相关上下文
    invoke_start = time.time()
    contexts = ensemble_retriever.invoke(query)
    invoke_elapsed = time.time() - invoke_start
    dedup_start = time.time()
    seen_context_keys = set()
    deduplicated_contexts = []
    for doc in contexts:
        context_key = (doc.metadata.get("source"), doc.page_content)
        if context_key in seen_context_keys:
            continue
        seen_context_keys.add(context_key)
        deduplicated_contexts.append(doc)
    contexts = deduplicated_contexts
    dedup_elapsed = time.time() - dedup_start
    print(
        f"[search_kb timing] kb_name={kb_name}, doc_count={doc_count}, "
        f"faiss_load={faiss_load_elapsed:.4f}s, docstore={docstore_elapsed:.4f}s, "
        f"bm25_build={bm25_elapsed:.4f}s, invoke={invoke_elapsed:.4f}s, "
        f"dedup={dedup_elapsed:.4f}s"
    )
    # 将检索到的上下文转化为一个字典，包含上下文的来源和内容
    contexts = {
        "results":[{"source":context.metadata.get("source",""),"page_contents":context.page_content,"rank":rank,"filename":context.metadata.get("filename"),"chunk_id":context.metadata.get("chunk_id")} for rank,context in enumerate(contexts, start=1)],
    }
    return contexts

# 列出所有知识库的API
@kbapp.get("/list_kb")
async def list_kbs(db: Session = Depends(get_db)):
    user_list = list_kb_from_db(db)
    result = [user['kb_name'] for user in user_list]
    return result

# # 程序主入口。如果不写入口函数，需要使用uvicorn命令执行
# # 定义主函数可以使用python运行
# if __kb_name__ == "__main__":
#     # 导入unicorn服务器的包
#     import uvicorn

#     # 运行服务器
#     uvicorn.run("User_FastAPI:app", host="127.0.0.1", port=6605, log_level="info", reload=True)
