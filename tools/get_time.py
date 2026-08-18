from datetime import datetime
import pytz

# class Get_time:
#     def run(self, text: str):
#         # 指定中国时区
#         tz = pytz.timezone('Asia/Shanghai')
#         current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
#         return current_time

# get_time = Get_time()

class Get_time:
    def run(self,text: str):
        #指定中国时区
        tz = pytz.timezone('Asia/Shanghai')
        current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
        return current_time
    
get_time = Get_time()