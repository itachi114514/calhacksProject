import asyncio
import os

import websockets
import aiohttp
import logging
from typing import AsyncGenerator
from dotenv import load_dotenv
load_dotenv()

# --- 配置 ---
WEBSOCKET_URI = "ws://localhost:8768?name=TTS_Module"  # WebSocket 服务器 URI
TTS_URL = "http://127.0.0.1:9880/tts"  # TTS API 端点 URL
REF_AUDIO_PATH = os.getenv("REF_AUDIO_PATH")  # 参考音频文件路径
REF_PROMPT_TEXT = os.getenv("REF_PROMPT_TEXT")  # 参考音频文件路径


BUFFER_SIZE = 4096  # 读取/发送音频块的大小

# --- 日志设置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 队列和事件 ---
sentence_queue = asyncio.Queue()  # 用于存储从 WebSocket 接收到的句子
shutdown_event = asyncio.Event()  # 事件，用于信号通知优雅关闭

# --- 辅助函数 ---
async def generate_tts_audio_stream(session: aiohttp.ClientSession, text: str) -> AsyncGenerator[bytes, None]:
    """
    调用 TTS API，异步返回音频数据流。
    使用参考的 payload 配置来适配你的需求。
    """
    payload = {
        "text": text,
        "text_lang": "en",
        "ref_audio_path": REF_AUDIO_PATH,
        "aux_ref_audio_paths": [],
        "prompt_text": REF_PROMPT_TEXT,
        "prompt_lang": "zh",
        "top_k": 5,
        "top_p": 1,
        "temperature": 1,
        "text_split_method": "cut0",
        "batch_size": 1,
        "batch_threshold": 0.75,
        "split_bucket": True,  # 注意：布尔值 True，非字符串 "True"
        "speed_factor": 1.0,
        "streaming_mode": True,  # 注意：布尔值 True，非字符串 "True"
        "seed": -1,
        "parallel_infer": True,  # 注意：布尔值 True，非字符串 "True"
        "repetition_penalty": 1.35
    }
    logging.info(f"正在请求 TTS 转换: {text[:30]}...")
    try:
        # 使用 aiohttp 进行异步请求
        async with session.post(TTS_URL, json=payload) as response:
            if response.status != 200:
                logging.error(f"TTS API 错误: {response.status} - {await response.text()}")
                return  # 如果请求出错，则不返回任何数据

            logging.info(f"TTS 流媒体开始：{text[:30]}...")
            # 逐块流式处理响应内容
            async for chunk in response.content.iter_chunked(BUFFER_SIZE):
                if shutdown_event.is_set():
                    logging.info("已收到关闭信号，停止 TTS 流。")
                    break
                if chunk:  # 确保块不为空
                    # Ensure chunk is not empty
                    # --- IMPORTANT ---
                    # Add your specific chunk processing logic here if needed
                    # e.g., parsing headers like `b'data'` if your TTS API uses them.
                    # This example assumes `chunk` is directly usable audio data.
                    # Example of simple filtering (if needed):
                    # if is_silent(chunk): # Assuming you have an is_silent function
                    #     continue
                    yield chunk  # 返回音频数据块
            logging.info(f"TTS 流媒体完成：{text[:30]}.")

    except aiohttp.ClientError as e:
        logging.error(f"连接 TTS API 时发生错误: {e}")
    except Exception as e:
        logging.error(f"生成 TTS 时发生异常: {e}")

# --- 核心任务 ---
async def receive_sentences(websocket):
    """监听来自 WebSocket 服务器的句子，并将其放入队列中。"""
    logging.info("句子接收任务已启动。")
    try:
        while not shutdown_event.is_set():
            async for message in websocket:
                if shutdown_event.is_set():
                    logging.info("接收到关闭信号，停止句子接收。")
                    break
                if isinstance(message, str):
                    if message.startswith("SAY:") :
                        if message[4:] == "true":
                            sentence_queue._queue.clear()  # 如果 SAY 为 true，清空队列
                        continue
                    logging.info(f"接收到句子: {message[:50]}...")
                    await sentence_queue.put(message)
                else:
                    logging.warning(f"接收到非文本消息: {type(message)}")
    except websockets.exceptions.ConnectionClosedOK:
        logging.info("WebSocket 连接正常关闭。")
    except websockets.exceptions.ConnectionClosedError as e:
        logging.error(f"WebSocket 连接关闭错误: {e.code} {e.reason}")
    except Exception as e:
        logging.error(f"句子接收过程中发生错误: {e}")
    finally:
        logging.info("句子接收任务结束。")
        if not shutdown_event.is_set():
            logging.warning("接收任务异常结束，发送关闭信号。")
            shutdown_event.set()

async def process_and_send_audio(websocket, session: aiohttp.ClientSession):
    """从队列中获取句子，生成 TTS 音频，并将音频流发送回 WebSocket。"""
    logging.info("TTS 处理和发送任务已启动。")
    while not shutdown_event.is_set():
        try:
            # Wait for a sentence from the queue, with a timeout to allow checking shutdown_event

            sentence = await asyncio.wait_for(sentence_queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue  # 如果没有收到句子，继续检查关闭信号
        except Exception as e:
            logging.error(f"从队列获取句子时发生错误: {e}")
            continue

        logging.info(f"正在处理句子: {sentence[:50]}...")
        audio_stream = generate_tts_audio_stream(session, sentence)

        try:
            async for audio_chunk in audio_stream:
                if shutdown_event.is_set():
                    logging.info("接收到关闭信号，停止发送音频。")
                    break
                if not websocket.state.OPEN:
                    logging.warning("WebSocket 已关闭，停止发送音频。")
                    shutdown_event.set()
                    break
                try:
                    await websocket.send(audio_chunk)  # 发送音频数据块
                except websockets.exceptions.ConnectionClosed:
                    logging.warning("WebSocket 在发送音频时关闭。")
                    shutdown_event.set()
                    break
                except Exception as e:
                    logging.error(f"发送音频块时发生错误: {e}")
                    break

            sentence_queue.task_done()  # 标记该句子已处理

        except Exception as e:
            logging.error(f"处理句子 '{sentence[:30]}...' 的音频流时发生错误: {e}")
            sentence_queue.task_done()

        if shutdown_event.is_set():
            break

    logging.info("TTS 处理和发送任务结束。")
    # Clear queue on shutdown? Optional.
    # while not sentence_queue.empty():
    #     sentence_queue.get_nowait()
    #     sentence_queue.task_done()

async def main():
    """主函数，连接 WebSocket 并启动任务。"""
    while True:
        try:
            websocket = None
            session = None
            tasks = []
            try:
                while True:
                    async with aiohttp.ClientSession() as session:
                        while not shutdown_event.is_set():
                            try:
                                logging.info(f"尝试连接 WebSocket: {WEBSOCKET_URI}")
                                websocket = await websockets.connect(WEBSOCKET_URI)
                                logging.info("WebSocket 连接成功。")

                                receiver_task = asyncio.create_task(receive_sentences(websocket))
                                sender_task = asyncio.create_task(process_and_send_audio(websocket, session))
                                tasks = [receiver_task, sender_task]

                                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

                                for task in done:
                                    try:
                                        task.result()
                                    except Exception as e:
                                        logging.error(f"任务结束时发生异常: {e}")

                                logging.info("任务结束，通常是连接关闭或发生错误。发送关闭信号。")
                                shutdown_event.set()
                                break

                            except (websockets.exceptions.WebSocketException, OSError, aiohttp.ClientError) as e:
                                logging.error(f"连接失败: {e}. 5秒后重试...")
                                await asyncio.sleep(5)
                            except Exception as e:
                                logging.error(f"主连接循环中发生意外错误: {e}")
                                shutdown_event.set()
                                break
                    shutdown_event.clear()
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                logging.info("主任务被取消。")
            finally:
                logging.info("启动关闭过程...")
                #shutdown_event.set()

                for task in tasks:
                    if not task.done():
                        task.cancel()
                        try:
                            await asyncio.wait_for(task, timeout=2.0)
                        except asyncio.TimeoutError:
                            logging.warning(f"任务 {task.get_name()} 未能正常取消。")
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logging.error(f"任务取消过程中发生错误: {e}")

                if websocket and websocket.state.OPEN:
                    logging.info("关闭 WebSocket 连接。")
                    await websocket.close()

                logging.info("关闭完成。")

        except Exception as e:
            print('远程服务端中断，尝试重新连接')


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("接收到 KeyboardInterrupt，正在关闭。")
        shutdown_event.set()
