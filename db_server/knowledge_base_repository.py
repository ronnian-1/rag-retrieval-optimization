from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
# from UserBase import User, session,Know
from db_server.base import Know,session

def add_kb_to_db(session: Session, kb_name: str,kb_info: str):
    try:
        res = session.query(Know).filter(Know.kb_name.ilike(kb_name)).first()
        if not res:
            new_res = Know(kb_name=kb_name,kb_info=kb_info)
            session.add(new_res)
            session.commit()
            return {"mess ": f"Know '{kb_name}' created successfully."}
        else:
            return {"mess ": f"Know '{kb_name}' already exists."}
    except Exception as e:
        session.rollback()
        return {"mess ": f"Error: {e}"}

def del_kb_from_db(session: Session, kb_name: str):
    try:
        res = session.query(Know).filter_by(kb_name=kb_name).first()
        if res:
            session.delete(res)
            session.commit()
            return {"mess": f"知识库 '{kb_name}' 删除成功！"}
        else:
            return {"mess": f"知识库 '{kb_name}' 不存在！"}
    except Exception as e:
        session.rollback()
        return {"mess": f"Error: {e}"}

def list_kb_from_db(session: Session):
    all_Know = session.query(Know).all()
    return [{"kb_name": k.kb_name, "kb_info": k.kb_info} for k in all_Know]


