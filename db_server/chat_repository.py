from db_server.base import ChatHistory, session

def save_chat(session_id, question, answer, db):

    new_chat = ChatHistory(
        session_id=session_id,
        question=question,
        answer=answer
    )

    db.add(new_chat)
    db.commit()
