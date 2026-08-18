from db_server.base import ChatHistory, session

def save_chat(session_id, question, answer):

    new_chat = ChatHistory(
        session_id=session_id,
        question=question,
        answer=answer
    )

    session.add(new_chat)
    session.commit()