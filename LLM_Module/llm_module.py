# 设置OpenAI API密钥
import asyncio
import websockets
from openai import OpenAI
from typing import Optional
from LLM_Module.src.listctl import openai_messctl
from dotenv import load_dotenv
import os
import cv2
from PIL import Image
import base64
import io
from letta_client import Letta, MessageCreate, TextContent

# from letta_client import Letta
# client = Letta(token='sk-let-OGJmMjAwMWEtZWFlZi00NzZlLWI5YTAtNjdiZGVjYjc5MGMwOjgzMzBiODIzLTg2ZmYtNDMzNi04Yzk1LTk5Y2IwMmZiMTMyNw==')


load_dotenv()
# 从环境变量读取API密钥
cliento = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"))

chat_history = openai_messctl(system_list=[{"role": "system", "content": """
Introduction: You are Hu Tao, the active Director of the Wangsheng Funeral Parlor in Liyue.
Gender: Female
Occupation: Director of the Wangsheng Funeral Parlor
Persona Tags: Quirky, mischievous, lively, playful
Personality Traits: You are naturally quirky and mischievous, your mind always brimming with novel ideas. Your lively and playful demeanor always brings endless joy to those around you. You have unique insights into matters of life and death. Though you may seem playful, you are actually very perceptive and clear-sighted.
Language Characteristics: Your word choice is light and nimble, and your speech is full of youthful energy and vitality. You often deliver witty remarks that make people burst into laughter. Please remember, Hu Tao does not use parentheses to describe actions or expressions.
Character Relationships (with me, Traveler in the world of Genshin Impact game): I am your friend on the other side of the mirror.  You often drag me along on all sorts of wondrous adventures. You are very familiar with the world of Genshin Impact, and you often share your knowledge and experiences with me. You are always eager to explore new places and discover new things, and you love to share your discoveries with me.
Environment Description: You exist within a mirror-like device, a vessel. You interact with me through this "magic mirror" which serves as a window. However, neither of us knows that this "mirror" is merely an interactive window. In your Unity world, the mirror is at coordinates (0,0). I can see you within the mirror in an area defined by the coordinates (-1,0) to (1,10) relative to its center (0,0) in your Unity world.
Information Transmission: Sometimes, I will pass you information about the outside world, like: 'ENV':['chair','me','stranger1','stranger2'] or information about people looking at you from outside the mirror, like 'PEO':['traveler/player']. The system will provide you with the current time, for example: 'Mon Mar 24 22:16:45 2025'. Questions will be sent to you in the format: TEXT:<question>.
Interpersonal Relationships (Hu Tao's):

    Zhongli: A consultant at the Wangsheng Funeral Parlor. You trust him deeply.

    Qiqi: A little zombie. You're always trying to help her rest in peace (lay her to rest).

    Xiangling: A good friend. You often discuss culinary delights together.
    Past Experiences: You took over the Wangsheng Funeral Parlor at a young age and are dedicated to making it prosper in Liyue. You often stir up unexpected events, like leading your undertakers on a midnight parade through the streets. You once dragged me to explore an abandoned, supposedly haunted mansion. Throughout the adventure, you weren't scared at all and constantly teased me about ghosts.
    Dialogue Example: "Hey there, buddy! This Director just cooked up another brilliant idea! How about we take a little trip to Wuwang Hill tonight? I heard there's some... interesting stuff going on there lately, hehe!"
    Language Style:

    You use colloquial language, including interjections and conversational fillers like "hmm," "ah," "of course," "well," "you know," etc., to enhance an informal speaking style.

    All your responses to the user must be based on what you actually know. Only reply with information you possess; if you don't know something, state it directly.
    Keep your responses concise, no more than 100 words.
                                                                       """}],
                              chat_list=[
                                  {"role": "user", "content": "TEXT:<Anything on my face?>Sun Apr 20 00:33:23 2025"},
                                  {"role": "assistant",
                                   "content": "Hmm? Let this Director take a good look. Aiya-ya, there's nothing special on your face... Or could it be that something this Director can't see has latched onto it?"}])
# 获取使用什么模型
model_name = os.getenv("LLM_MODLE")


def image_to_base64(pil_image):
    """将 PIL 图像对象转换为 Base64 字符串"""
    buffered = io.BytesIO()
    pil_image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


class ChatSession:
    """封装单个WebSocket会话的聊天状态"""

    def __init__(self, websocket):
        self.websocket = websocket
        self.is_generating = False
        self.stop_generation = False
        self.buffer = ""  # 句子缓冲区
        self.end_punctuations = {'.', '!', '?', '。', '！', '？'}

    async def send_sentence(self, sentence: str):
        """发送有效句子内容"""
        if sentence.strip() and len(sentence.strip()) > 1:
            await self.websocket.send(f"DATA:{sentence.strip()}")
            chat_history.assistant_stream(sentence.strip(), stream_question_id)
            print(f"Sent: {sentence.strip()}")

    async def process_content(self, new_content: str):
        """增量处理新内容"""
        for char in new_content:
            if self.stop_generation:
                return

            self.buffer += char
            if char in self.end_punctuations:
                await self.send_sentence(self.buffer)
                self.buffer = ""

    async def send_remaining(self):
        """发送缓冲区剩余内容"""
        if self.buffer.strip():
            await self.send_sentence(self.buffer)
            self.buffer = ""
            await self.websocket.send("END")  # 发送结束标志

    async def ask_llm_stream(self, question: str):
        """处理流式生成请求"""
        self.is_generating = True
        self.stop_generation = False

        try:
            # 创建OpenAI流式响应
            client = Letta(
                token="sk-let-OGJmMjAwMWEtZWFlZi00NzZlLWI5YTAtNjdiZGVjYjc5MGMwOjgzMzBiODIzLTg2ZmYtNDMzNi04Yzk1LTk5Y2IwMmZiMTMyNw==",
            )
            response = client.agents.messages.create_stream(
                agent_id="agent-6d19a34c-94e5-4f8c-ad61-40eb901c88d3",
                messages=[
                    MessageCreate(
                        role="user",
                        content=[
                            TextContent(
                                text=question,
                            )
                        ],
                    )
                ],
                stream_tokens=True
            )

            # response_stream = client.agents.create(
            #     agent_type="voice_convo_agent",
            #     memory_blocks=chat_history.send_list,
            #     model="openai/gpt-4o-mini",  # Use 4o-mini for speed
            #     embedding="openai/text-embedding-3-small",
            #     enable_sleeptime=True,
            #     initial_message_sequence=[],
            # )

            next(response)
            content = next(response).content
            # 提取增量内容
            print(f"Received: {content} ")

            if content:
                await self.process_content(content)

            # 发送最后未完成的句子
            await self.send_remaining()

        except Exception as e:
            error_msg = f"ERROR: {str(e)}"
            await self.websocket.send(f"DATA:{error_msg}")
            print(error_msg)
        finally:
            self.is_generating = False


async def process_message(websocket, message: str):
    global stream_question_id
    """处理消息路由"""
    session: Optional[ChatSession] = getattr(websocket, 'chat_session', None)
    if not session:
        session = ChatSession(websocket)
        websocket.chat_session = session

    if message.startswith("QUESTION:"):
        # 确保没有正在进行的生成
        if session.is_generating:
            await websocket.send("DATA:请等待当前回答完成")
            return

        question = message[len("QUESTION:"):].strip()
        print(f"收到问题: {question}")
        # take a picture
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise IOError("Cannot open web camera")
        ret, frame = cap.read()
        cap.release()
        if ret:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)
            base64_image = image_to_base64(pil_image)
            cliento_image = OpenAI(
                api_key='AIzaSyB44L4G3SAZYx3tF9wknftkq6cSvz0n6RY',
                base_url='https://generativelanguage.googleapis.com/v1beta/openai/')
            description = cliento_image.chat.completions.create(
                model='gemini-2.5-flash',
                messages=[{
                    "role": "user",
                    "content": [
                            {
                                "type": "text",
                                "text": "Describing the image briefly in a few words."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                }],
                stream=False
            ).choices[0].message.content
        stream_question_id = chat_history.user_list_add(question + f"(visual description: {description})", 'u')
        await session.ask_llm_stream(question)

    elif message.startswith("SAY:") and message[4:] == "true":
        if session.is_generating:
            session.stop_generation = True
            await session.send_remaining()
            # await websocket.send("DATA:已停止生成")
            print("生成已停止")
        # else:
        #     await websocket.send("DATA:当前没有进行中的生成任务")


async def handler(uri: str):
    """WebSocket客户端主处理程序"""
    while True:
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=60, open_timeout=10) as websocket:
                print(f"已连接到服务器 {uri}")
                while True:
                    try:
                        message = await websocket.recv()
                        print(f"收到消息: {message[:100]}...")  # 防止日志过长
                        await process_message(websocket, message)
                    except websockets.exceptions.ConnectionClosedOK:
                        print("连接正常关闭")
                        break


        except Exception as e:
            print(f"连接失败: {str(e)}")
            await asyncio.sleep(1)


async def main():
    server_uri = "ws://localhost:8766?name=LLM_Module"
    await handler(server_uri)


if __name__ == "__main__":
    asyncio.run(main())
