import os
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from configs.settings import SQLALCHEMY_DATABASE_URI

# 创建数据库引擎，这里使用的是 SQLite. SQLALCHEMY_DATABASE_URI=sqlite:///./db_server/data/info.db
# echo=True ：可选参数，默认值为 False。True 时，将所有发送到数据库的SQL语句输出到控制台。有助于调试了解数据库操作的细节
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=True)

# 创建基类，所有模型都将继承自这个基类
# 当定义一个模型类时，继承这个基类后，SQLAlchemy 会自动将类中的属性映射到表中的列。
Base = declarative_base()

# 定义 Know 模型
class Know(Base):
    __tablename__ = 'knowledge_bases'  # /db_server/data/info.db中的表名。
    # 定义表中的列，包括类型，约束，字段说明
    id = Column(Integer, primary_key=True, autoincrement=True, comment="ID")  # 主键
    kb_name = Column(String(50), comment="知识库名称")  # 
    kb_info=Column(String(50),comment="知识库描述")

    # 返回一个字符串，用于表示对象的字符串表示形式。当打印或查看对象时，会调用这个方法来获取对象的字符串表示
    def __repr__(self):
        return f"<Know(id='{self.id}', kb_name='{self.kb_name}', kb_info='{self.kb_info}')>"
    

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True)
    session_id = Column(String(100))
    role = Column(String(20))   # ⭐关键：admin / user

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, autoincrement=True)

    session_id = Column(String(100), comment="会话ID")

    question = Column(String(1000), comment="用户问题")

    answer = Column(String(5000), comment="AI回答")

    def __repr__(self):
        return f"<ChatHistory(session_id='{self.session_id}')>"

# #定义Stu模型
# class Stu(Base):
#     __tableKb_name__ = "stu_table"
#     id = Column(Integer,primary_key=True,autoincrement=True,comment="ID")
#     Kb_name = Column(String(50),comment="姓名")
#     age=Column(Integer,comment="年龄")
#     sex=Column(String(50),comment="性别")

#     def __repr__(self):
#         return f"<Stu(id='{self.id}', Kb_name='{self.Kb_name}', age='{self.age}',sex='{self.sex}')>"
#
# # 创建所有表，第一次执行创建标，如果表结构已经存在，再次执行这行代码不会对数据库产生任何影响，它不会重复创建已经存在的表。
# 如果模型改变，增加列，修改列的类型或者约束，再次执行会更新数据库中的表结构
Base.metadata.create_all(engine)

# 创建会话
# sessionmaker 用于创建会话工厂（Session Factory）。会话工厂可以生成多个会话实例，都绑定到同一个数据库引擎（engine）
# 通过这个会话工厂创建的会话实例都可以使用这个引擎与数据库进行交互
Session = sessionmaker(bind=engine)
# 这个会话实例 session 是应用程序与数据库之间交互的接口。
# 它提供了执行数据库操作的方法，例如添加数据、查询数据、提交事务、回滚事务等。方便地操作数据库中的表和数据。
session = Session()


def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()
