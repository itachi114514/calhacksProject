import asyncio
import websockets
import numpy as np
import webrtcvad
import sounddevice as sd
from funasr import AutoModel
import pickle as pkl
import torch
from torch import nn
from websockets.protocol import State
import inspect
import logging
from openai import OpenAI
import json

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.FileHandler("../audio_forwarder_buffered.log"), # Changed log file name
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ActionControl")

# --- llm 配置 ---
cliento = OpenAI(
    api_key='sk-etJYxlyBK66y20GrVu3AXfr1dZjZw5EqFKrkoTBpR39ByrK3',
    base_url="https://api.kksj.org/v1")


class ActionControl:
    def __init__(self, server_uri):
        # 链接
        self.server_uri = server_uri
        self.websocket = None

    async def connect_to_server(self):
        """连接到 WebSocket 服务器"""
        self.websocket = await websockets.connect(self.server_uri, ping_interval=None)
        print(f"Connected to WebSocket Server: {self.server_uri}")

    async def client_listener(self):

        while True:
            try:
                async with websockets.connect(self.server_uri,
                                              ping_interval=20,
                                              ping_timeout=10,  # 心跳响应超时
                                              open_timeout=3,  # 连接建立超时3秒
                                              close_timeout=1  # 关闭超时1秒
                                              ) as websocket:
                    self.websocket = websocket  # 保存连接对象

                    logger.info(f"Receiver: Successfully connectedt to {self.server_uri}")
                    print(f"[ActionControl] 成功连接到 {self.server_uri}")
                    async for message in websocket:
                        print(message)
                        if isinstance(message, str) and message.startswith("QUESTION:"):
                            print(1)
                            ret, action = await self.judge_intention(message.replace("QUESTION:", ""))
                            if ret:
                                print(f"【触发指令】 {action}")
                                await self.send_text(json.dumps(action))
            except Exception as e:
                logger.error(f"Connection error: {str(e)}")
                await asyncio.sleep(1)  # 等待后重连

    async def judge_intention(self, question):
        system_prompt = """
           【"任务"】: "请你扮演一个专业的用户意图识别器，请分析一下用户的提问{{QUESTION}}识别意图{{intents}}并以json格式输出："
【"思维链"】
required_intents= ["场景切换", "视角切换", "跳舞", "移动","其他"]
{{intents}} in required_intents
    required_intents 的定义和取值解释: {
        "场景切换": 用户期望切换场景，场景取值：【客厅、书房】，
        "视角切换":用户期望切换视角，视角取值：【0~11】
        "跳舞":用户期望跳舞，或者不想她跳舞，跳舞取值:【dance、notdance】
        "移动": 用户期望移动，跳舞取值:【转圈圈、左转、右转、还原】
        "其他": 用户的提问与上述都无关或者取值不对
      }
【"示例"】
示例输入：
请你向左转
示例输出：
{"移动":"左转"}
【要求】
简短迅速的回复
           """
        print(12)
        # 创建OpenAI流式响应
        res = cliento.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ]
        )
        text = res.choices[0].message.content
        text_json = json.loads(text)
        print(13)
        print(text_json)
        if '其他' in text_json:
            return False, {}
        else:
            # 将自然语言翻译成实际代码取值。
            action = await self.explain(text_json)
            print(action)
            return True, action

    async def explain(self, text_json):
        ViewIndex = {}
        for i in range(1, 12):
            ViewIndex[str(i)] = {"NeedChangeView": True, "ViewIndex": i}
        ViewIndex['3'] = str(3)
        action_dict = {
            "场景切换": {"客厅": {"Scene": "RoomScene"},
                         "书房": {"Scene": "RoomScene2"}
                         },
            "视角切换": ViewIndex,
            "跳舞": {"dance": {"CanDancing": True, "Dancing": "HuTaoDancing1"},
                     "notdance": {"CanDancing": False}},
            "移动": {"左转": {"NeedMove": True, "MovePos": {"X": -1, "Y": 1, "Z": 1}},
                     "右转": {"NeedMove": True, "MovePos": {"X": 1, "Y": 1, "Z": 1}},
                     "还原": {"NeedMove": True, "MovePos": {"X": 1, "Y": 1, "Z": 1}},
                     "转圈圈": {"NeedMove": True, "MovePos": {"X": 1, "Y": 1, "Z": 1}}
                     },
            "其他": {"其他": "异常"}
        }

        print(text_json)
        # 取第一个key
        key = next(iter(text_json))
        print(key)
        try:
            action = action_dict[key][text_json[key]]
        except Exception as e:
            print("ERROR", str(e))
            try:
                if key == "场景切换":
                    action = action_dict[key]["书房"]
                elif key == "视角切换":
                    action = action_dict[key]["5"]
                elif key == "移动":
                    action = action_dict[key]["转圈圈"]
            except:
                print("ERROR2", str(e))
                print(1)
        return action

    async def send_text(self, text):
        """发送json给server"""
        if self.websocket:
            await self.websocket.send("Action:" + text)
            await asyncio.sleep(0.01)

    async def test(self):
        """测试函数，以文字输入代替转录输入，并直接发送到服务器"""
        while True:
            text = input('user:')
            ret, action = self.judge_intention(text)
            if ret:
                print(f"【触发指令】 {action}")
                await self.send_text(json.dumps(action))

    async def run(self):
        #   await self.connect_to_server()
        await self.client_listener()

        # 是否需要手动输入测试
        # await self.test()


async def main():
    # 实例化并运行
    action_control = ActionControl('ws://localhost:8771?name=Action_Module')
    await action_control.run()


if __name__ == '__main__':
    asyncio.run(main())
