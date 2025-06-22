# -*- coding: UTF-8 -*-
'''
@Project :virtual_idol_system
@File    :idle_story_module.py
@Author  :智能助手
@Contack :技术支持邮箱
@Version :V1.2
@Date    :2024-04-20
@Describe: 虚拟偶像待机剧情状态机模块
'''
import asyncio
import random
import json
import time
from enum import Enum
from typing import Dict, Optional
import websockets
import logging

# --- 配置 ---
WEBSOCKET_URI = "ws://localhost:8772?name=Agent_Module"  # WebSocket 服务器 URI
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("IdleStoryModule")


# 状态枚举
class IdleState(Enum):
    START = "开始"
    INIT = "初始化"
    CAT_INTERACTION = "与猫互动"
    SHY_REACTION = "害羞反应"
    SITTING = "坐下休息"
    DANCE_PREP = "舞蹈准备"
    DANCING = "跳舞中"
    RETURN_IGIN = "返回原点"


# 定时器管理
class StoryTimer:
    def __init__(self, min_delay: int, max_delay: int):
        self.min = min_delay
        self.max = max_delay
        self._start_time = 0.0
        self._duration = 0.0

    def start(self):
        """启动定时器并生成随机持续时间"""
        self._duration = random.uniform(self.min, self.max)
        self._start_time = time.time()
        logger.debug(f"定时器启动 持续时间: {self._duration:.1f}s")

    def is_expired(self) -> bool:
        """检查定时器是否到期"""
        return (time.time() - self._start_time) >= self._duration

    def remaining(self) -> float:
        """剩余时间"""
        return max(self._duration - (time.time() - self._start_time), 0)


# 待机剧情控制器
class IdleStoryController:
    def __init__(self, ws_client):
        self.ws_client = ws_client
        self.current_state = IdleState.START
        self.timers = {
            "start_trigger": StoryTimer(2, 4),
            'main_trigger': StoryTimer(30, 60),
            'sitting': StoryTimer(30, 100),
            'dance_prep': StoryTimer(20, 40)
        }
        self.random_behavior_interval = 10
        self._current_view = 10
        self._is_interrupted = False

    async def send_unity_command(self, command: Dict):
        """发送指令到Unity"""
        try:
            if self.ws_client.websocket and self.ws_client.websocket.state.OPEN:
                await self.ws_client.send("Agent:" + json.dumps(command))
                logger.info(f"已发送指令: {command}")
        except Exception as e:
            self.ws_client.websocket = self.ws_client.websocket.connect_to_server()
            logger.error(f"指令发送失败: {str(e)}")

    async def reset_state(self):
        """重置到初始状态"""
        self.current_state = IdleState.START
        self._is_interrupted = False
        await self.send_unity_command({
            "PresetPoint": "Origin_Point",
            "NeedChangeView": True,
            "ViewIndex": random.choice([0, 3, 7, 10]),
            "OpenRandomBehaviour": True,
            "RandomBehaviourInterval": self.random_behavior_interval
        })
        logger.info("状态已重置到初始化")

    async def handle_interruption(self):
        """处理用户中断"""
        self._is_interrupted = True
        await self.send_unity_command({
            "ClearAudioStream": True,
            "StopAnimation": True,
            "Movement": "Idle01_Breathing"
        })
        logger.warning("检测到用户中断，正在恢复初始状态...")
        await self.reset_state()

    async def play_animation_sequence(self):
        """播放动画序列"""
        await self.send_unity_command({"CanDancing": True,
                                       "Dancing": "HuTaoDancing1"})
        await asyncio.sleep(100)  # 基础动画时长

    async def state_machine(self):
        """状态机主循环"""
        while True:
            if self._is_interrupted:
                await asyncio.sleep(1)
                continue

            try:
                match self.current_state:
                    case IdleState.START:
                        await self.handle_start_state()
                    case IdleState.INIT:
                        await self.handle_init_state()
                    case IdleState.CAT_INTERACTION:
                        await self.handle_cat_interaction()
                    case IdleState.SHY_REACTION:
                        await self.handle_shy_reaction()
                    case IdleState.SITTING:
                        await self.handle_sitting()
                    case IdleState.DANCE_PREP:
                        await self.handle_dance_prep()
                    case IdleState.DANCING:
                        await self.handle_dancing()

                await asyncio.sleep(0.1)  # 防止CPU过载

            except Exception as e:
                logger.error(f"状态机异常: {str(e)}", exc_info=True)
                await self.reset_state()

    async def handle_start_state(self):
        if not self.timers['start_trigger']._start_time:
            print('开始执行，状态初始化的工作')
            self.timers['start_trigger'].start()

        if self.timers['start_trigger'].is_expired():
            logger.info("开始执行初始化")
            self.timers['start_trigger']._start_time = 0.0
            self.current_state = IdleState.INIT

    async def handle_init_state(self):
        """初始化状态处理"""

        if not self.timers[
            'main_trigger']._start_time and self.ws_client.websocket and self.ws_client.websocket.state.OPEN:
            print('开始执行，状态初始化的工作')
            self.timers['main_trigger'].start()
            await self.send_unity_command({
                "PresetPoint": "Origin_Point",
                "NeedChangeView": True, "ViewIndex": 10,
                "OpenRandomBehaviour": True, "RandomBehaviourSwitchingIntervals": 2
            })

        if self.timers['main_trigger'].is_expired():
            logger.info("触发猫咪互动剧情")
            self.current_state = IdleState.CAT_INTERACTION

    async def handle_cat_interaction(self):
        """与猫互动处理"""
        await self.send_unity_command({
            "SetCatMeow": False,
            "NeedSetCatMeow": True})

        # time.sleep(20)
        #
        # await self.send_unity_command({
        #     "PresetPoint": "LapTop_Point", "PresetBehaviour": "Companion_Cat11"})

        self.current_state = IdleState.SHY_REACTION
        time.sleep(10)

    async def handle_shy_reaction(self):
        """害羞反应处理"""
        await self.send_unity_command({"PresetBehaviour": "Shy"})
        time.sleep(10)
        self.current_state = IdleState.SITTING
        self.timers['sitting'].start()

    async def handle_sitting(self):
        """坐下状态处理"""
        if self.timers['sitting'].is_expired():
            await self.send_unity_command({
                "PresetPoint": "Chair_Point",
                "PresetBehaviour": "Sit_Down"
            })
            time.sleep(10)
            self.current_state = IdleState.DANCE_PREP
            self.timers['dance_prep'].start()

    async def handle_dance_prep(self):
        """舞蹈准备处理"""
        if self.timers['dance_prep'].is_expired():
            await self.send_unity_command({"PresetBehaviour": "Sit_Up"})
            time.sleep(2)
            await self.send_unity_command({"PresetPoint": "Origin_Point"})
            self.current_state = IdleState.DANCING

    async def handle_dancing(self):
        """跳舞状态处理"""
        # await self.play_animation_sequence()
        await self.reset_state()


# WebSocket客户端增强版
class AgentWSClient:
    def __init__(self, server_uri: str):
        self.server_uri = server_uri
        self.story_controller: Optional[IdleStoryController] = None
        self.websocket = None

    def connect_to_server(self):
        """连接到 WebSocket 服务器"""
        self.websocket = websockets.connect(self.server_uri, ping_interval=None)
        print(f"Connected to WebSocket Server: {self.server_uri}")
        return self.websocket

    async def handle_message(self, message: str):
        """增强的消息处理"""
        if message.startswith("USER_CMD:"):
            cmd = message.split(":")[1]
            if cmd == "STOP_DANCE":
                if self.story_controller:
                    await self.story_controller.handle_interruption()
        elif message == "CONNECTION_READY":
            await self.init_story_controller()

    async def init_story_controller(self):
        """初始化剧情控制器"""
        self.story_controller = IdleStoryController(self)
        asyncio.create_task(self.story_controller.state_machine())
        logger.info("待机剧情控制器已启动")

    async def client_listener(self):
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

    async def send(self, text):
        await self.websocket.send(text)

    async def run(self):
        await  self.init_story_controller()
        await self.client_listener()


# 使用示例
async def main():
    # 实例化并运行
    agent_websocket = AgentWSClient(WEBSOCKET_URI)

    await agent_websocket.run()


if __name__ == "__main__":
    asyncio.run(main())
