from db_server.base import User, session
import uuid

# def login_user(username):

#     user = session.query(User).filter_by(username=username).first()

#     if user:
#         return user.session_id

#     session_id = str(uuid.uuid4())

#     new_user = User(
#         username=username,
#         session_id=session_id
#     )

#     session.add(new_user)
#     session.commit()

#     return session_id



def login_user(username):

    user = session.query(User).filter(
        User.username == username
    ).first()

    if not user:

        role = "user"

        if username == "admin":
            role = "admin"

        user = User(
            username=username,
            session_id=str(uuid.uuid4()),
            role=role
        )

        session.add(user)
        session.commit()

    return {
        "message": "登录成功",
        "role": user.role
    }