import json
import os
import requests
import gradio as gr

base_url="http://127.0.0.1:6605"

def create_kb(kb_name,kb_info):
    # 定义API的URL
    url  =base_url+"/kbs/create_kb"
    # 定义请求数据
    data={
        "kb_name":kb_name,
        "kb_info": kb_info
    }
    # 发送POST请求
    try:
        response = requests.post(url,json=data)
        print("==========================create kb response:", response)
        print("原始响应内容:", response.text)  # 新增调试代码
        # 检查相迎状态码
        if response.status_code==200:
            # return gr.update(value="知识库创建成功！",visible=True),gr.update(value=""),gr.update(value="")
            message = response.json().get("message", "创建成功")
            return gr.update(value=message, visible=True), gr.update(value=""), gr.update(value="")
        else:
            return gr.update(value=f"知识库创建失败：{response.json().get('detail','')}",visible=True),gr.update(value=""),gr.update(value="")
    except Exception as e:
        return gr.update(value=f"请求失败：{e}",visible=True),gr.update(value=""),gr.update(value="")
    


def delete_kb(selected_name):
    url = base_url + "/kbs/delete_kb"
    try:
        if not selected_name:
            return gr.update(value="请选择知识库！", visible=True)

        # # 确保传递的是姓名字符串
        # if isinstance(selected_name, dict) and "value" in selected_name:
        #     name_to_delete = selected_name["value"]
        # else:
        #     name_to_delete = selected_name

        # 从显示字符串中提取名字（格式：张三-18-男）
        # 用 split('-') 分割，取第一个元素作为名字
        name_to_delete = selected_name.split('-')[0]

        response = requests.delete(url, params={"kb_name": name_to_delete})
        print("==========================delete kb response:", response)
        print("==========================delete kb response.json:", response.json())

        if response.status_code == 200:
            msg = response.json().get("mess", "删除成功！")
            
            # # 翻译成中文显示
            # if "deleted successfully" in msg:
            #     # 提取名字
            #     name_in_msg = name_to_delete
            #     msg_cn = f"学生用户 '{name_in_msg}' 删除成功！"
            # elif "does not exist" in msg:
            #     msg_cn = f"学生用户 '{name_to_delete}' 不存在！"
            # else:
            #     msg_cn = msg  # 其他信息保持原样
            # 翻译成中文显示
            # if "deleted successfully" in msg:
            #     msg_cn = f" 知识库：'{name_to_delete}' 删除成功！"
            # elif "does not exist" in msg:
            #     msg_cn = f"知识库：'{name_to_delete}' 不存在！"
            # else:
            #     msg_cn = msg

            return gr.update(value=msg, visible=True)
        else:
            return gr.update(value=f"删除失败：{response.text}", visible=True)
    except Exception as e:
        return gr.update(value=f"请求失败：{e}", visible=True)

def list_kb():
    # 定义API的URL
    list_kb_url=base_url+"/kbs/list_kb"
    # 发送GET请求
    response=requests.get(list_kb_url)
    # 检查响应码状态码并打印结果
    if response.status_code == 200:
        print("==========================list kb response:", response)
        kb_list = response.json() #解析json格式的知识库列表
        print("==========================", response)
        print("==========================", kb_list)
    #     display_list = [
    # {"label": f"{kb['name']}-{kb[' ']}-{kb[' description']}", "value": kb['name']}
#     for kb in kb_list
# ]
        display_list=kb_list
        return gr.update(
            choices=display_list,
            value=display_list[0] if display_list else None
            )
    else:
        return gr.update(choices=[], value=None)
    
# 选择文件
# 全局文件列表
selected_files=[]
def update(file):
    if file:
        # 将新选中的文件添加到列表中
        for f in file:
            if f not in selected_files:
                selected_files.append(f)
    return gr.update(value=selected_files,visible=True),gr.update(value=[])

# 点击按钮，上传
def upload_docs(kb_name_upload,file_upload,chunk_size,chunk_overlap):
    # 定义API的URL
    upload_docs_url=base_url+"/kbs/upload_docs"
    # 构建文件和表单数据
    files=[('files',(open(file_path,"rb"))) for file_path in file_upload if os.path.getsize(file_path)>0]
    if not files:
        return gr.update(value=f"上传所有文件，全部内容为空",visible=True),gr.update(value=[],visible=False)
    
    data={
        'kb_name':kb_name_upload,
        'chunk_size':chunk_size,
        'chunk_overlap':chunk_overlap
    }

    # 点击别的知识库，不会显示刚刚上传的文件
    global selected_files
    selected_files=[]
    # 发送post请求
    try:
        # 发送post请求
        response=requests.post(upload_docs_url,files=files,data=data)

        # 检查响应状态码并输出结果
        if response.status_code==200:
            return gr.update(value="文件上传成功",visible=True),gr.update(value=[],visible=False)
        else:
            return gr.update(value=f"文件上传失败,状态码：{response.status_code},错误信息:{response.json().get('detail','')}",
                             visible=True),gr.update(value=[],visible=False)
    except Exception as e:
        return gr.update(value=F"请求失败:{e}",visible=True),gr.update(value=[],visible=False)
