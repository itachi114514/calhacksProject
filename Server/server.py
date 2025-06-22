import asyncio
import websockets
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
import os
load_dotenv()
# 共享状态
state = {"say": False,"generating": False}
clients = set()
clients_dict = dict()
# 是否显示更多debug过程
verbose=os.getenv("VERBOSE")

async def notify_clients():
    state["generating"] = False
    """广播 say 状态给所有客户端"""
    if clients:
        message = f"SAY:{'true' if state['say'] else 'false'}"
        await asyncio.gather(*[client.send(message) for client in clients])

def handler_decorator(func):
    async def wrapper(websocket):
        """处理 WebSocket 连接"""
        try:
            clients.add(websocket)
            uri = websocket.request.path
            parsed_url = urlparse(uri)
            query_params = parse_qs(parsed_url.query)

            # 获取身份参数，默认为 "unknown"
            name = query_params.get("name", ["unknown"])[0]
            assert name in ["ASR_Module", "LLM_Module", "Unity_Module", "TTS_Module","Interaction_Module","Action_Module","Agent_Module"]
            print(f"[network] {name} connected: {websocket.remote_address} ")
            clients_dict[name] = websocket
            await func(websocket)
        except Exception as e:
            print(f"[network] Error: Module {name} Describe {str(e)}")
        finally:
            clients.remove(websocket)
    return wrapper

@handler_decorator
async def asrModule_handler(websocket):
    async for message in websocket:
        if message.startswith("SWITCH_STATE"):
            state["say"] = not state["say"]
            if verbose:
                print(f"[ASR] State updated: {state['say']}")

            await notify_clients()

        elif message.startswith("DATA:"):
            state["generating"]= True
            # 普通字节流传输
            print(f"[ASR] Received Data: {message[5:]}")
          # await clients_dict["LLM_Module"].send("QUESTION:" + message[5:])
            await asyncio.gather(
                         clients_dict["LLM_Module"].send("QUESTION:" + message[5:]),
                         clients_dict["Action_Module"].send("QUESTION:" + message[5:])
                    )

@handler_decorator
async def llmModule_handler(websocket):
    async for message in websocket:
        if message.startswith("SWITCH_STATE"):
            state["say"] = not state["say"]
            if verbose:
                print(f"[LLM] State updated: {state['say']}")
            await notify_clients()

        elif message.startswith("DATA:"):
            # 普通字节流传输
            print(f"[LLM] Received Data: {message[5:]}")
            await clients_dict["TTS_Module"].send(message[5:])
        elif message.startswith("END:"):
            state["generating"] = False

@handler_decorator
async def unityModule_handler(websocket):
    # await websocket.send(f"SAY:{'true' if state['say'] else 'false'}")
    async for message in websocket:
        print(f"[Unity] Received message: {message}")

@handler_decorator
async def ttsModule_handler(websocket):
    audio_buffer = bytearray()

    try:
        async for chunk in websocket:
            #print(f"Received message: {chunk}")
            data_index = chunk.find(b'data')
            if data_index != -1:
                await clients_dict["Unity_Module"].send("SWITCH_ACTION")
                data_size_start = data_index + 4
                data_size = int.from_bytes(chunk[data_size_start:data_size_start + 4], byteorder='little')
                if data_size != 0:
                    audio_buffer.extend(chunk[data_size_start + 4:])
                    await clients_dict["Unity_Module"].send(chunk[data_size_start + 4:])
            else:
                audio_buffer.extend(chunk)
                await clients_dict["Unity_Module"].send(chunk)

    except Exception as e:
        pass
    '''finally:
        # 保存为wav文件
        import wave
        with wave.open("output.wav", "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(32000)
            wf.writeframes(audio_buffer)'''

@handler_decorator
async def interactionModule_handler(websocket):
    async for message in websocket:
        if message.startswith("DATA:") and not state["generating"]:
            # 普通字节流传输
            print(f"Received Data: {message[5:]}")
            await clients_dict["LLM_Module"].send("QUESTION:"+message[5:]+"正在看着你")
        elif message.startswith("END:"):
            state["generating"] = False

@handler_decorator
async def Action_handler(websocket):
    async for message in websocket:
        print("[Action]",message)
        start_action = "Action:"
        instruction=message.replace(start_action,"") # 指令
        if message.startswith(start_action):
            # 向unity传输指令
            print(f"[Action] Received instruction: {instruction}")
            await clients_dict["Unity_Module"].send(message)
@handler_decorator
async def Agent_handler(websocket):
    async for message in websocket:
        print("[Agent]",message)
        start_action = "Agent:"
        instruction=message.replace(start_action,"") # 指令
        if message.startswith(start_action):
            # 向unity传输指令
            print(f"[Agent] Received instruction: {instruction}")
            await clients_dict["Unity_Module"].send(message)
async def main():
    components = [
        {"name": "ASR_Module", "port": 8765, "handler": asrModule_handler},
        {"name": "LLM_Module", "port": 8766, "handler": llmModule_handler},
        {"name": "Unity_Module", "port": 8767, "handler": unityModule_handler},
        {"name": "TTS_Module", "port": 8768, "handler": ttsModule_handler},
        {"name": "Interaction_Module", "port": 8770, "handler": interactionModule_handler},
        {"name": "Action_Module", "port": 8771, "handler": Action_handler},
        {"name": "Agent_Module", "port": 8772, "handler": Agent_handler},
    ]
    # 创建所有 WebSocket 服务器（并等待它们启动）
    servers = [await websockets.serve(component["handler"], "localhost", component["port"],ping_interval=None,ping_timeout=None) for component in components]

    print("All WebSocket servers are running...")

    # 让所有服务器保持运行
    await asyncio.gather(*[server.wait_closed() for server in servers])

asyncio.run(main())
