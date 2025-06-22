import asyncio
import json
import logging
import websockets
import io # We might not need io directly, bytearray is sufficient
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK, ConnectionClosedError
import random
import requests

# --- 配置 ---
LISTENER_URI = "ws://localhost:8767?name=Unity_Module"  # 我们作为客户端连接这里，接收音频
SERVER_HOST = "0.0.0.0"             # 我们作为服务端监听的地址
SERVER_PORT = 8769                  # 我们作为服务端监听的端口
CHUNK_SIZE = 4096                   # 每次从 buffer 读取并发送的大小
BUFFER_WARN_THRESHOLD = 1024 * 1024 * 5 * 1024# 5 MB Buffer size warning threshold

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        #logging.FileHandler("../audio_forwarder_buffered.log"), # Changed log file name
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AudioForwarderBuffered")

# --- 全局变量 ---
# 用于存储当前连接到我们服务器(8769)的客户端WebSocket连接
active_server_client_connection = None
# 异步锁，用于保护对 active_server_client_connection 的访问
connection_lock = asyncio.Lock()

# 音频数据缓冲区
audio_buffer = bytearray()
# 异步锁，用于保护对 audio_buffer 的并发访问
buffer_lock = asyncio.Lock()
# 事件，用于通知发送者有新数据可读
data_available_event = asyncio.Event()


async def change_movement():
    # movement = ["Idle01_Breathing",
    #     "Idle02_LookLeftAndRight",
    #     "Idle03_LookAtHands",
    #     "Idle04_LookAtFeet",
    #     "Idle05_Stretch",
    #     "Idle06_ComeUpWithAnIdea",
    #     "Talk00",
    #     "Talk01",
    #     "Think00",
    #     "Think01",
    #     "WaveHandSlightly"]

    movement = ["Maid_Standing_Pose_",
                "Stretching_",
                "Slap_",
                "Light_Hopping_",
                "Tiptoe_and_Wave_",
                "Scare_",

                "Somersault_",
           ]
    return {"Movement": random.choice(movement)}


# --- 服务端处理逻辑 (监听 8769) ---
async def server_handler(websocket: websockets.WebSocketServerProtocol):
    """处理连接到我们服务端(8769)的客户端连接状态"""
    global active_server_client_connection
    client_address = websocket.remote_address
    logger.info(f"Server: Client connected from {client_address}")
    print(f"[服务端 8769] 客户端 {client_address} 已连接")

    async with connection_lock:
        # 如果已有连接，可以考虑关闭旧的（根据需求）
        if active_server_client_connection and not active_server_client_connection.state.OPEN:
            logger.warning(f"Server: Closing previous connection {active_server_client_connection.remote_address} "
                           f"due to new connection from {client_address}")
            print(f"[服务端 8769] 注意：新的连接 {client_address} 导致旧连接 {active_server_client_connection.remote_address} 被替换")
            try:
                await active_server_client_connection.close(code=1000, reason="New connection replaced")
            except ConnectionClosed:
                logger.debug("Previous connection already closed.")
            except Exception as e:
                logger.error(f"Error closing previous connection: {e}", exc_info=False)

        # 存储新的活动连接
        active_server_client_connection = websocket
        logger.info(f"Server: Active client set to {client_address}")

    try:
        # 保持连接开放，等待客户端断开或被替换
        # 这个 handler 现在只管理连接状态，不发送数据
        await websocket.wait_closed()
    except ConnectionClosedOK:
        logger.info(f"Server: Client {client_address} disconnected cleanly.")
        print(f"[服务端 8769] 客户端 {client_address} 已正常断开")
    except ConnectionClosedError as e:
        logger.warning(f"Server: Client {client_address} connection closed with error: {e}")
        print(f"[服务端 8769] 客户端 {client_address} 连接错误断开: {e}")
    except Exception as e:
        logger.error(f"Server: Error with client {client_address}: {e}", exc_info=True)
        print(f"[服务端 8769] 客户端 {client_address} 发生意外错误: {e}")
    finally:
        logger.info(f"Server: Cleaning up connection for {client_address}")
        # 清理连接引用，只有当断开的是当前活动连接时才清理
        async with connection_lock:
            if active_server_client_connection is websocket:
                active_server_client_connection = None
                logger.info(f"Server: Active client cleared ({client_address})")
                print(f"[服务端 8769] 活动客户端连接已清除 ({client_address})")
            else:
                 logger.info(f"Server: Disconnected client {client_address} was not the active one.")


# --- 客户端处理逻辑 (连接 8767 - 接收并写入 Buffer) ---
async def client_listener():
    """作为客户端连接到 8767，接收数据并写入共享 buffer"""
    global audio_buffer
    while True:
        logger.info(f"Receiver: Attempting to connect to listener at {LISTENER_URI}...")
        print(f"[接收端 8767] 尝试连接到 {LISTENER_URI}...")
        try:
            # 使用较高的 ping 超时，防止因网络波动轻易断开
            async with websockets.connect(LISTENER_URI, ping_interval=20, ping_timeout=60, open_timeout=10) as websocket:
                logger.info(f"Receiver: Successfully connected to {LISTENER_URI}")
                print(f"[接收端 8767] 成功连接到 {LISTENER_URI}")

                async for message in websocket:
                    # 确保接收到的是 bytes
                    if isinstance(message, bytes):
                        #asyncio.create_task(change_movement())
                        async with buffer_lock:
                            audio_buffer.extend(message)
                            buffer_len = len(audio_buffer)
                            # logger.debug(f"Receiver: Received {len(message)} bytes. Buffer size: {buffer_len}")
                            # 只有当 buffer 至少有一个 chunk 时才设置事件
                            if buffer_len >= CHUNK_SIZE:
                                data_available_event.set() # 通知发送者有足够数据
                            if buffer_len > BUFFER_WARN_THRESHOLD:
                                logger.warning(f"Receiver: Buffer size ({buffer_len} bytes) exceeds threshold ({BUFFER_WARN_THRESHOLD} bytes)")
                                print(f"[警告] 缓冲区大小 {buffer_len / 1024 / 1024:.2f} MB 超过阈值 {BUFFER_WARN_THRESHOLD / 1024 / 1024:.2f} MB")

                    elif isinstance(message, str) and message.startswith("SAY:") :
                        # 回到待机状态
                        if active_server_client_connection:
                            await active_server_client_connection.send(json.dumps({"ClearAudioStream":True}))
                            print("[服务端 8769] 打断unity，清空缓冲区}")
                        audio_buffer.clear() # 清空 buffer
                        data_available_event.clear() # 清除事件
                        logger.info("Receiver: Received SAY:false, clearing buffer and data available event.")
                        print("[接收端 8767] 收到 SAY:false，清空缓冲区和数据可用事件")
                        continue

                    elif isinstance(message, str) and message.startswith("SWITCH_ACTION"):
                        if active_server_client_connection:
                            movement = await change_movement()
                            await active_server_client_connection.send(json.dumps(movement))
                            # logger.info(f"Receiver: Sent movement data to server: {movement}")
                            print(f"[服务端 8769] 发送动作数据给Unity: {movement}")
                    elif isinstance(message, str) and str(message).startswith("Action:"):
                        if active_server_client_connection:
                            message = message.replace("Action:", '')
                            await active_server_client_connection.send(message)
                            # logger.info(f"Receiver: Sent movement data to server: {movement}")
                            print(f"[服务端 8769] 发送动作数据给unity: {message}")
                    elif isinstance(message, str) and str(message).startswith("Agent:"):
                        if active_server_client_connection:
                            message = message.replace("Agent:", '')
                            await active_server_client_connection.send(message)
                            # logger.info(f"Receiver: Sent movement data to server: {movement}")
                            print(f"[服务端 8769] 发送动作数据给unity: {message}")
                    else:
                        print(message)
                        logger.warning(f"Receiver: Received non-bytes message type: {type(message)}. Ignoring.")
                        print(f"[接收端 8767] 收到非字节数据: {type(message)}，已忽略。")

        except websockets.exceptions.ConnectionClosed as e:
             logger.warning(f"Receiver: Connection to {LISTENER_URI} closed: {e}. Retrying in 5 seconds...")
             print(f"[接收端 8767] 连接关闭: {e}. 5秒后重试...")
        except asyncio.TimeoutError:
             logger.warning(f"Receiver: Connection attempt to {LISTENER_URI} timed out. Retrying in 5 seconds...")
             print(f"[接收端 8767] 连接超时. 5秒后重试...")
        except Exception as e:
            logger.error(f"Receiver: Error connecting or communicating with {LISTENER_URI}: {e}. Retrying in 5 seconds...", exc_info=True)
            print(f"[接收端 8767] 连接或通信错误: {e}. 5秒后重试...")
        finally:
            # 清理 buffer 和事件状态以防万一 (虽然理论上 sender 会处理)
            # async with buffer_lock:
            #    audio_buffer.clear()
            # data_available_event.clear()
            # logger.info("Receiver: Cleared buffer and event on disconnect/error.")
            await asyncio.sleep(5) # 等待后重连

# --- 发送逻辑 (从 Buffer 读取并发送给 8769 客户端) ---
async def server_sender():
    """独立的任务，不断从 buffer 读取数据并发送给当前连接的 8769 客户端"""
    global audio_buffer, active_server_client_connection
    logger.info("Sender: Task started.")
    print("[发送端 8769] 发送任务已启动")
    while True:
        try:
            # 1. 等待有足够数据的信号
            await data_available_event.wait()

            # 2. 获取当前连接的客户端
            conn = None
            async with connection_lock:
                conn = active_server_client_connection

            # 3. 如果有客户端连接
            if conn:
                chunk_to_send = None
                # 4. 锁定并操作 buffer
                async with buffer_lock:
                    if len(audio_buffer) >= CHUNK_SIZE:
                        chunk_to_send = bytes(audio_buffer[:CHUNK_SIZE]) # 复制一份
                        del audio_buffer[:CHUNK_SIZE] # 从 buffer 中移除已读取的部分
                        buffer_len = len(audio_buffer)
                        # logger.debug(f"Sender: Read {len(chunk_to_send)} bytes. Remaining buffer: {buffer_len}")

                        # 如果 buffer 中剩余数据不足一个 chunk，清除事件，等待新数据
                        if buffer_len < CHUNK_SIZE:
                            data_available_event.clear()
                            # logger.debug("Sender: Buffer below chunk size, cleared data available event.")
                    else:
                        # 虽然被事件唤醒，但可能数据被其他地方消耗或刚好不够，清除事件
                        data_available_event.clear()
                        # logger.debug("Sender: Woke up but not enough data, cleared event.")

                # 5. 发送数据 (在 buffer_lock 之外)
                if chunk_to_send:
                    try:
                        await conn.send(chunk_to_send)
                        # logger.debug(f"Sender: Sent {len(chunk_to_send)} bytes to {conn.remote_address}")
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning(f"Sender: Failed to send, client {conn.remote_address} disconnected.")
                        print(f"[发送端 8769] 发送失败，客户端 {conn.remote_address} 可能已断开")
                        # server_handler 的 finally 块会处理 active_server_client_connection 的清理
                        # 清除事件，因为当前没有有效连接可以发送了
                        data_available_event.clear()
                    except Exception as e:
                        logger.error(f"Sender: Error sending data to {conn.remote_address}: {e}", exc_info=False) # Reduce log noise
                        print(f"[发送端 8769] 发送数据时出错: {e}")
                        # 同样，清除事件可能比较安全
                        data_available_event.clear()
            else:

                # 没有活动连接，清除事件，等待新连接和新数据
                if data_available_event.is_set():
                     logger.debug("Sender: No active client connection, clearing data available event.")
                     data_available_event.clear()
                # 短暂休眠避免空轮询（虽然 event.wait 应该阻塞）
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Sender: Unexpected error in main loop: {e}", exc_info=True)
            print(f"[发送端 8769] 发送任务发生意外错误: {e}")
            # 在循环中遇到错误，短暂暂停后继续尝试
            await asyncio.sleep(1)


# --- 主程序 ---
async def main():
    """启动服务端和客户端"""
    logger.info("Starting Buffered Audio Forwarder...")
    print("启动带缓冲的音频转发器...")
    print(f"  - 作为服务端监听: ws://{SERVER_HOST}:{SERVER_PORT}")
    print(f"  - 作为客户端连接: {LISTENER_URI}")
    print(f"  - 转发块大小: {CHUNK_SIZE} bytes")

    # 启动 WebSocket 服务端 (监听 8769)
    server = await websockets.serve(server_handler, SERVER_HOST, SERVER_PORT)
    logger.info(f"Server is listening on ws://{SERVER_HOST}:{SERVER_PORT}")
    print("[服务端 8769] 已启动并监听")

    # 创建并运行客户端接收任务 (连接 8767, 写入 buffer)
    receiver_task = asyncio.create_task(client_listener(), name="ReceiverTask")

    # 创建并运行服务端发送任务 (读取 buffer, 发送给 8769 client)
    sender_task = asyncio.create_task(server_sender(), name="SenderTask")

    # 等待任务完成 (理论上它们会一直运行，除非出错或程序关闭)
    try:
        # 等待两个核心任务完成
        done, pending = await asyncio.wait(
            [receiver_task, sender_task],
            return_when=asyncio.FIRST_COMPLETED, # 任何一个任务结束就退出等待
        )

        # 如果有任务结束了，记录原因
        for task in done:
            try:
                # 获取任务结果或异常
                task.result()
                logger.info(f"Task {task.get_name()} finished normally.")
                print(f"[任务管理] 任务 {task.get_name()} 正常结束。")
            except asyncio.CancelledError:
                 logger.info(f"Task {task.get_name()} was cancelled.")
                 print(f"[任务管理] 任务 {task.get_name()} 被取消。")
            except Exception as e:
                logger.critical(f"Task {task.get_name()} failed critically: {e}", exc_info=True)
                print(f"[任务管理] 任务 {task.get_name()} 严重失败: {e}")

        # 取消仍在运行的任务
        for task in pending:
            task.cancel()
            logger.info(f"Cancelling pending task {task.get_name()}")
            print(f"[任务管理] 取消挂起任务 {task.get_name()}")
        if pending:
             await asyncio.wait(pending) # 等待取消完成


    except asyncio.CancelledError:
        logger.info("Main task cancelled, shutting down other tasks.")
        print("[主程序] 主任务被取消，正在关闭其他任务...")
        if not receiver_task.done(): receiver_task.cancel()
        if not sender_task.done(): sender_task.cancel()
        # 等待任务响应取消
        await asyncio.gather(receiver_task, sender_task, return_exceptions=True)

    finally:
        logger.info("Shutting down server...")
        print("[服务端 8769] 正在关闭...")
        server.close()
        await server.wait_closed()
        logger.info("Server shut down.")
        print("[服务端 8769] 已关闭")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown signal received (KeyboardInterrupt).")
        print("\n收到关闭信号 (Ctrl+C)，正在退出...")
    except Exception as e:
        logger.critical(f"Unhandled exception in main execution: {e}", exc_info=True)
        print(f"主程序发生未处理错误: {e}")
    finally:
        logger.info("Buffered Audio Forwarder stopped.")
        print("带缓冲的音频转发器已停止.")