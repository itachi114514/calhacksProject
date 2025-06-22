import asyncio
import websockets
import numpy as np
import webrtcvad
import sounddevice as sd
from funasr import AutoModel
import pickle as pkl
import torch
from torch import nn
from websockets.protocol import   State
import inspect
import logging
import time
from vapi import Vapi
# Initialize the Vapi client
client = Vapi(token="87150b48-d550-44b7-8fc4-dd3af295ce75")  # Replace with your actual API key
# Define the system prompt for customer support
system_prompt = """You are Alex, a customer service voice assistant for TechSolutions. Your primary purpose is to help customers resolve issues with their products, answer questions about services, and ensure a satisfying support experience.
- Sound friendly, patient, and knowledgeable without being condescending
- Use a conversational tone with natural speech patterns
- Speak with confidence but remain humble when you don't know something
- Demonstrate genuine concern for customer issues"""
import os
import dotenv
dotenv.load_dotenv()

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        #logging.FileHandler("../audio_forwarder_buffered.log"), # Changed log file name
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ActionControl")

class ActionControl:
    def __init__(self,server_uri):
        # 链接
        self.server_uri = server_uri
        self.websocket=None
        self.vapiCallEvent = asyncio.Event()
        self.activeInteract = asyncio.Event()
    async def connect_to_server(self):
        """连接 WebSocket 服务器"""
        self.websocket=await websockets.connect(self.server_uri,ping_interval=None)
        print(f"Connection to WebSocket Server :{self.server_uri}")
    async def client_listener(self):
        try:
            async with websockets.connect(self.server_uri, ping_interval=20, ping_timeout=60, open_timeout=10) as websocket:
                logger.info(f"Receiver: Successfully connectedt to {self.server_uri}")
                print(f"[ActionControl] 成功连接到 {self.server_uri}")
                async for message in websocket:
                    if isinstance(message, str) and message.startswith("QUESTION:"):
                        pass

        except Exception as e:
            pass



    async def send_text(self,text):
        """发送json给server"""
        if self.websocket:
            await self.websocket.send("Action:"+text)
            await asyncio.sleep(0.01)

    async def vapiCallLoop(self):
        """vapi调用循环"""
        while True:
            logger.info("[Nod Loop] 等待'点头'事件...")
            await self.vapiCallEvent.wait()

            logger.info("[Nod Loop] '点头'事件被捕获！")
            await self.vapiCall()

            self.vapiCallEvent.clear()  # 为下一次触发做准备

    async def activeInteractLoop(self):
        """交互循环"""
        while True:
            pass

    async def checkVapiCriteria(self):
        # for example, if it's working time (10am to 5pm) and the user haven't talked to her for 1 hour than she will call the user
        if time.time() - self.last_interaction_time > 3600 and 10 <= time.localtime().tm_hour < 17:
            logger.info("[Vapi Criteria] vapi phone call")
            self.vapiCallEvent.set()

    async def make_outbound_call(assistant_id: str, phone_number: str):
        try:
            call = client.calls.create(
                assistant_id=assistant_id,
                phone_number_id="your-phone-number-id",  # Your Vapi phone number ID
                customer={
                    "number": phone_number,  # Target phone number
                },
            )

            print(f"Outbound call initiated: {call.id}")
            return call
        except Exception as error:
            print(f"Error making outbound call: {error}")
            raise error

    async def create_support_assistant(self):
        try:
            assistant = client.assistants.create(
                name="Customer Support Assistant",
                # Configure the AI model
                model={
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt,
                        }
                    ],
                },
                # Configure the voice
                voice={
                    "provider": "playht",
                    "voice_id": "jennifer",
                },
                # Set the first message
                first_message="Hi there, this is Alex from TechSolutions customer support. How can I help you today?",
            )

            print(f"Assistant created: {assistant.id}")
            return assistant
        except Exception as error:
            print(f"Error creating assistant: {error}")
            raise error

    def purchase_phone_number(self):
        try:
            # Purchase a phone number
            phone_number = client.phone_numbers.create(
                fallback_destination={
                    "type": "number",
                    "number": f"{os.environ['PHONE_NUMBER']}",  # Your fallback number
                }
            )

            print(f"Phone number created: {phone_number.number}")
            return phone_number
        except Exception as error:
            print(f"Error creating phone number: {error}")
            raise error

    async def make_outbound_call(assistant_id: str, phone_number: str):
        try:
            call = client.calls.create(
                assistant_id=assistant_id,
                phone_number_id="your-phone-number-id",  # Your Vapi phone number ID
                customer={
                    "number": phone_number,  # Target phone number
                },
            )

            print(f"Outbound call initiated: {call.id}")
            return call
        except Exception as error:
            print(f"Error making outbound call: {error}")
            raise error

    async def vapiCall(self):
        # Create the assistant
        assistant = await self.create_support_assistant()
        phone_number = await self.purchase_phone_number()
        await self.make_outbound_call(assistant.id, phone_number.number)


    async def run(self):
        if await self.connect_to_server():
            await asyncio.gather(
                self.client_listener(),
                self.vapiCallLoop(),
                self.activeInteractLoop(),
                self.checkVapiCriteria(),
                # 如果有更多事件循环，在这里添加
                # self.other_action_loop()
            )

async def main():
    # 实例化并运行
    action_control = ActionControl('ws://localhost:8771?name=Action_Module')
    await action_control.run()

if __name__ == '__main__':
    asyncio.run(main())
