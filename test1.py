# from tools.knowledge_search import knowledgebas_search
# print(knowledgebas_search.run("myknown1,黑熊精自称是什么"))

# from db_server.knowledge_base_repository import del_kb_from_db
# from db_server.knowledge_base_repository import list_kb_from_db
# from db_server.base import session
# if __name__ == "__main__":
#     # del_kb_from_db(session, "b")
#     data =  list_kb_from_db(session)
#     print(data)

from db_server.base import session
from db_server.knowledge_base_repository import del_kb_from_db

result = del_kb_from_db(session, "泳装尺码相关")
print(result)