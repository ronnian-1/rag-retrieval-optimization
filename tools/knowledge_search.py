import json
import requests
from pydantic import Field
from configs.settings import TIME_OUT

# 知识库搜索工具类
class KnowledgeBaseSearch:
    inputs: str = Field(description="包含知识库名称和需要查询问题的字符串")

    def run(self,inputs):
        kb_name,query = inputs.split(",", 1)
        print(f"==========================",kb_name,query)
        url = "http://127.0.0.1:6605/kbs/search_kb"

        # 请求体数据
        data = {
            "kb_name":kb_name,
            "query":query
        }

        # 将数据转换为Json格式
        json_data = json.dumps(data)

        # 设置请求头，指定发送的数据格式为JSON
        headers={
            'Content-Type':'application/json'
        }

        # 发送Post请求
        response = requests.post(url,data=json_data,headers=headers,timeout=TIME_OUT)
        print(f"==========================",response)

        # 如果请求成功，解析返回数据
        if response.status_code == 200:
            data = response.json()

            # 获取知识库信息
            res="".join([f"source:\n{d['source']}\ncontext:\n{d['page_contents']}\n" for d in data['results']])
            return res
        else:
            return f"无法获取和{query}有关的信息"

knowledgebas_search = KnowledgeBaseSearch()

