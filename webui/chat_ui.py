# from webui.chat_with_agent_api import chat_with_backend_api
# import json


# def chat_ui(message,
#             sys_prompt, history_len,
#             temperature, top_p,
#             max_tokens, stream):

#     data = {
#         "query": message,
#         "sys_prompt": sys_prompt,
#     }

#     response = chat_with_backend_api(data, stream)

#     answer = ""

#     for chunk in response:
#         answer = chunk
#         yield answer