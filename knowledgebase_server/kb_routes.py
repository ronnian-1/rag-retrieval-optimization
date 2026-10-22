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
import tempfile
import logging

from langchain_community.document_loaders import TextLoader

# app = FastAPI()

kbapp = APIRouter(prefix="/kbs",  tags=["kbs managerment"])
logger = logging.getLogger(__name__)

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
    """Validate the whole batch, skip identical files, and reject name conflicts.

    Catchable commit failures roll back new originals and replaced index files.
    shortcut: two index files are not a crash-safe transaction; readers can
    observe a commit in progress. Incomplete rollback keeps recovery files
    and the upload lock for manual recovery.
    """
    if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
        raise HTTPException(status_code=400, detail="Require chunk_size > 0 and 0 <= chunk_overlap < chunk_size")
    if not files:
        raise HTTPException(status_code=400, detail="No files supplied")

    kb_name = safe_kb_name(kb_name)
    kb_path = safe_kb_path(kb_name)
    kb_file_storage_path = safe_file_storage_path(kb_name)
    if not os.path.exists(kb_path):
        raise HTTPException(status_code=404, detail="Database not found")

    lock_path = kb_path + ".upload.lock"
    try:
        with open(lock_path, "x"):
            pass
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Knowledge base upload is busy or requires recovery")

    staging_dir = None
    transaction_state = "preparing"
    try:
        incoming = {}
        skipped_files = []
        for file in files:
            file_path, filename = safe_upload_path(kb_file_storage_path, file.filename)
            extension = os.path.splitext(filename)[1].lower()
            if extension not in data_loader.supported_extensions:
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {filename}")
            content = file.file.read()
            key = os.path.normcase(file_path)
            if key in incoming:
                if incoming[key][2] != content:
                    raise HTTPException(status_code=409, detail=f"Conflicting contents for filename: {filename}")
                skipped_files.append(filename)
                continue
            exists = os.path.exists(file_path)
            if exists:
                with open(file_path, "rb") as original:
                    if original.read() != content:
                        raise HTTPException(status_code=409, detail=f"Filename already exists with different content: {filename}")
            incoming[key] = (file_path, filename, content, exists)

        embedding_model = get_embedding_model()
        vectorstore = FAISS.load_local(kb_path, embedding_model, allow_dangerous_deserialization=True)
        indexed_names = {
            os.path.normcase(doc.metadata.get("filename", ""))
            for doc in vectorstore.docstore._dict.values()
        }
        pending = []
        for file_path, filename, content, exists in incoming.values():
            if os.path.normcase(filename) in indexed_names:
                if not exists:
                    raise HTTPException(status_code=409, detail=f"Indexed file has no original; recovery required: {filename}")
                skipped_files.append(filename)
            else:
                pending.append((file_path, filename, content, exists))

        if not pending:
            return {"message": "Identical files already indexed; nothing added", "added_files": [], "skipped_files": skipped_files}

        staging_dir = tempfile.mkdtemp(prefix=".upload-", dir=os.path.dirname(kb_path))
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ".", ",", "，", "。", ""]
        )
        prepared = []
        all_chunks = []
        for i, (file_path, filename, content, exists) in enumerate(pending):
            staged_file = os.path.join(staging_dir, f"{i}{os.path.splitext(filename)[1]}")
            with open(staged_file, "wb") as staged:
                staged.write(content)
            try:
                docs = data_loader().get_loader(staged_file).load()
                chunks = splitter.split_documents(docs)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Failed to parse or split file: {filename}") from exc
            if not chunks or not any(chunk.page_content.strip() for chunk in chunks):
                raise HTTPException(status_code=400, detail=f"No indexable text in file: {filename}")
            for idx, chunk in enumerate(chunks):
                chunk.metadata.update({"source": file_path, "kb_name": kb_name, "filename": filename, "chunk_id": idx})
            prepared.append((file_path, filename, staged_file, exists))
            all_chunks.extend(chunks)

        # Prepare the entire batch before touching originals or the live index.
        vectorstore.add_documents(all_chunks)
        staged_index = os.path.join(staging_dir, "index")
        vectorstore.save_local(staged_index)
        index_files = ("index.faiss", "index.pkl")
        for name in index_files:
            shutil.copy2(os.path.join(kb_path, name), os.path.join(staging_dir, name))

        created_files = []
        attempted_indexes = []
        creating_file = None
        try:
            transaction_state = "committing"
            os.makedirs(kb_file_storage_path, exist_ok=True)
            for file_path, filename, staged_file, exists in prepared:
                if not exists:
                    creating_file = file_path
                    try:
                        original = open(file_path, "xb")
                    except FileExistsError:
                        creating_file = None
                        raise
                    with original:
                        created_files.append(file_path)
                        with open(staged_file, "rb") as staged:
                            shutil.copyfileobj(staged, original)
                    creating_file = None
            for name in index_files:
                # Record intent first: an interrupt can follow a successful replace.
                attempted_indexes.append(name)
                os.replace(os.path.join(staged_index, name), os.path.join(kb_path, name))
            transaction_state = "committed"
        except BaseException as exc:
            transaction_state = "recovery_uncertain"
            rollback_errors = []
            interruption = exc if not isinstance(exc, Exception) else None
            if creating_file is not None and creating_file not in created_files and os.path.exists(creating_file):
                rollback_errors.append(RuntimeError("Original creation interrupted; ownership uncertain"))
            for name in reversed(attempted_indexes):
                try:
                    if not os.path.exists(os.path.join(staged_index, name)):
                        os.replace(os.path.join(staging_dir, name), os.path.join(kb_path, name))
                except BaseException as rollback_exc:
                    rollback_errors.append(rollback_exc)
                    if not isinstance(rollback_exc, Exception) and interruption is None:
                        interruption = rollback_exc
            for file_path in reversed(created_files):
                try:
                    os.remove(file_path)
                except BaseException as rollback_exc:
                    rollback_errors.append(rollback_exc)
                    if not isinstance(rollback_exc, Exception) and interruption is None:
                        interruption = rollback_exc
            if rollback_errors:
                logger.error("Upload rollback incomplete; uploads blocked. Lock: %s; recovery: %s; errors: %r",
                             lock_path, staging_dir, rollback_errors)
            else:
                transaction_state = "rolled_back"
            if interruption is not None:
                raise interruption
            if rollback_errors:
                raise HTTPException(status_code=500, detail=f"Upload rollback incomplete; uploads blocked. Recovery directory: {staging_dir}") from exc
            raise HTTPException(status_code=500, detail="Upload commit failed; originals and index rolled back") from exc

        added_files = [item[1] for item in prepared]
        return {"message": f"File'{added_files}' added to database '{kb_name}' successfully", "added_files": added_files, "skipped_files": skipped_files, "transaction_state": transaction_state}
    except HTTPException:
        raise
    except Exception as exc:
        detail = "Upload preparation failed; no changes committed" if transaction_state == "preparing" else f"Upload failed; transaction state: {transaction_state}"
        raise HTTPException(status_code=500, detail=detail) from exc
    finally:
        if transaction_state in ("preparing", "committed", "rolled_back"):
            if staging_dir is not None:
                try:
                    shutil.rmtree(staging_dir)
                except Exception:
                    logger.exception("Upload recovery cleanup failed; state=%s; recovery=%s", transaction_state, staging_dir)
            try:
                os.remove(lock_path)
            except Exception:
                logger.exception("Upload lock release failed; state=%s; uploads remain blocked; lock=%s", transaction_state, lock_path)
        else:
            logger.error("Upload recovery state uncertain; retaining lock=%s and recovery=%s", lock_path, staging_dir)

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
        retrievers=[bm25_retriever,faiss_retriever],weights=[0.3,0.7]
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
