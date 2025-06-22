import asyncio
import websockets
import numpy as np
import webrtcvad
import sounddevice as sd
import pickle as pkl
import torch
from torch import nn
from collections import deque, Counter
from dotenv import load_dotenv
import os
from tools.text_handle import clean_special_tags
load_dotenv()


class SpeechRecognizer:
    def __init__(self, server_uri,
                 model_type='speech'):
        self.server_uri = server_uri
        self.say = False
        self.model_type = model_type
        if model_type == 'Speech':
            from funasr import AutoModel
            model_path = "./src/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
            self.model = AutoModel(model=model_path, model_revision="v2.0.4",
                                   vad_model="fsmn-vad", vad_model_revision="v2.0.4",
                                   punc_model="ct-punc-c", punc_model_revision="v2.0.4",
                                   spk_model="cam++", spk_model_revision="v2.0.2",
                                   device="cuda")
            self.LANGUAGE = "zh"

        elif model_type == 'SenseVoice':
            from funasr import AutoModel
            model_path = './src/SenseVoiceSmall'
            self.model = AutoModel(model=model_path, model_revision="v2.0.4",
                                   vad_model="fsmn-vad", vad_model_revision="v2.0.4",
                                   punc_model="ct-punc-c", punc_model_revision="v2.0.4",
                                   # spk_model="cam++", spk_model_revision="v2.0.2",
                                   device="cuda")
            self.LANGUAGE = "zh"

        elif model_type == 'faster-whisper':
            from faster_whisper import WhisperModel
            self.model = WhisperModel("large-v3", device="cuda", compute_type="float16")
            self.LANGUAGE = "en"
            self.model.generate = lambda *args, **kwargs: self.model.transcribe(*args,  **kwargs)


        self.vad = webrtcvad.Vad(3)
        self.RATE = 16000
        self.CHUNK = int(self.RATE * (10 / 1000))
        self.MAX_QUEUE = 45  # 语言调整
        self.audio_buffer_deque = deque(maxlen=self.MAX_QUEUE)
        self.speech_history = deque(maxlen=self.MAX_QUEUE)


        self.MIN_TEXT_LENGTH = 3  # 最小转录文本长度
        self.DEVICE = 12
        self.stream = sd.InputStream(
            samplerate=self.RATE, channels=1, dtype=np.float32,
            blocksize=self.CHUNK,
            device=self.DEVICE
        )

        self.send_say_lock = asyncio.Lock()
        self.transcribe_audio_lock = asyncio.Lock()
        self.audio_buffer = np.array([])
        self.no_speech_counter = 0
        self.websocket = None
        self.cos_sim = nn.CosineSimilarity()
        self.noise_rms_queue=deque(maxlen=self.MAX_QUEUE)
        self.speak_rms_queue=deque(maxlen=self.MAX_QUEUE)


        self.NOISE_QUEUE_SIZE=self.MAX_QUEUE

        self.INITIAL_NOISE_THRESHOLD=0.20 # 最小声音阈值
        self.MAX_NOISE_THRESHOULD= float("inf") # 最大的声音阈值
        self.VALID_AUDIO_THRESHOLD = self.INITIAL_NOISE_THRESHOLD # 赋值最低有效声音大小为最小阈值
        self.speak_rms_queue.append(self.INITIAL_NOISE_THRESHOLD) # 添加一个值进去保障其一定不为空
        with open("src/embedding.pkl", "rb") as f:
            self.embedding = pkl.load(f)

    async def connect_to_server(self):
        """连接到 WebSocket 服务器"""
        self.websocket = await websockets.connect(self.server_uri, ping_interval=20, ping_timeout=60, open_timeout=10)
        print(f"Connected to WebSocket Server: {self.server_uri}")

    async def send_text(self, text):
        """发送转录文本到服务器"""
        if self.websocket:
            await self.websocket.send(f"DATA:{text}")


    async def send_text_if_long_enough(self, text):
        """发送转录文本到服务器，如果长度超过一定阈值"""
        if self.model_type == "SenseVoice":
            # 去除SenseVoice返回的多余输出
            text = clean_special_tags(text)
        print("转录文本：{}".format(text))
        if len(text) > self.MIN_TEXT_LENGTH:
            await self.send_text(text=text)
        else:
            print(f"<send_text_if_long_enough>: Text too short, and discarded: {text}")

    async def send_say_state(self):
        if self.websocket:
            await self.websocket.send(f"SWITCH_STATE")

    async def switch_state(self):
        """切换状态并发送"""
        async with self.send_say_lock:  # 使用锁来保证不会同时调用
            await self.send_say_state()
            self.say = not self.say

    def calculate_rms(self, audio_data):
        """计算音频数据的均方根值 (RMS)"""
        # 确保音频数据是浮点类型，避免整数溢出
        try:
            audio_data = np.asarray(audio_data, dtype=np.float64)

            # 检查是否为空数组，避免除以零
            if audio_data.size == 0:
                return 0.0

            # 计算RMS (均方根)
            return np.sqrt(np.mean(audio_data ** 2))
        except Exception as e:
            print(e)
            return 50.0

    def is_speech(self, audio_data):    # 未测试
        return np.sqrt(np.mean(audio_data ** 2)) > self.VALID_AUDIO_THRESHOLD
        """检测是否是语音 并考虑音量（自适应阈值版）"""
        speech_flag = self.vad.is_speech(audio_data.tobytes(), self.RATE)

        # 计算当前音频片段的RMS值
        rms = self.calculate_rms(audio_data)

        # 如果是非语音片段，更新噪音阈值
        if not speech_flag:
            self.noise_rms_queue.append(rms)  # 将RMS值添加到队列
            # print(f"无活动音频的阈值 {rms} {self.speech_history.count(0)}")
        else:
            self.speak_rms_queue.append(rms)
            print(f"活动音频的阈值 {rms} {self.speech_history.count(0)}")

        # 计算当前的噪音阈值
        if len(self.noise_rms_queue) == self.NOISE_QUEUE_SIZE:
            # 当队列填满时，计算阈值为平均值+2标差
            avg_noise_rms = np.mean(self.noise_rms_queue)
            std_noise_rms = np.std(self.noise_rms_queue)
            min_speak_rms=np.min(self.speak_rms_queue)

            self.VALID_AUDIO_THRESHOLD = min(self.MAX_NOISE_THRESHOULD,max(min_speak_rms+50,self.INITIAL_NOISE_THRESHOLD,avg_noise_rms + 2 * std_noise_rms))



        # 检查是否是语音
        if speech_flag: # 同时满足VAD检测和音量超过动态阈值

            speech_flag = rms > self.VALID_AUDIO_THRESHOLD

        return speech_flag

    async def transcribe_audio(self, audio_data):
        """使用模型转录音频"""
        try:
            async with self.transcribe_audio_lock:  # 使用锁来保证不会同时调用
                # sd.play(audio_data, samplerate=self.RATE, device=self.DEVICE)  # 播放音频
                kwargs = {}
                if self.model_type == "SenseVoice" or self.model_type == "Speech":
                    kwargs["output_timestamp"] = True
                print(0)
                audio_data = audio_data.astype(np.float32)  # 确保音频数据是float32类型
                segments = self.model.generate(audio_data, beam_size=5,
                                       best_of=5,
                                       temperature=0.0,language=self.LANGUAGE, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500,speech_pad_ms=400),**kwargs)
                # print(list(segments[0]))
                if self.model_type == "faster-whisper":
                    segments = list(segments[0])  # faster-whisper 返回的是生成器
                    segments = [{"text":segments[0].text}]
            if segments and segments[0]['text']:
                try:
                    if os.getenv("acoustic_fingerprint")!= "False":
                        dist = self.cos_sim(segments[0]["spk_embedding"],self.embedding)
                        if dist < 0.5:
                            print(f"{dist} lower than 0.5, ignored")
                            return
                    text = segments[0]['text']
                    #print(segments[0])
                    if self.model_type=="Speech":
                        speaker = segments[0]['sentence_info'][0]['spk']
                        print(f"Recognized: {text},Speaker: {speaker}")
                    # await self.send_text(f"TEXT:<{text}>CONF:<{dist}>")
                    await self.send_text_if_long_enough(f"{text}")
                    await asyncio.sleep(0.1)
                except:
                    print(segments)
        except Exception as e:
            print(e)
            pass

    async def test(self):
        """测试函数"""
        # 用于以文字输入代替语音并直接发送到服务器
        while True:
            text = input("Enter text to send: ")
            self.say = True
            await self.send_text(f"DATA:{text}")

    async def listen_and_transcribe(self, websocket):  # 未测试
        """监听麦克风并发送数据"""
        # await self.test()
        self.websocket = websocket
        print("🎙️ Listening...")
        self.stream.start()

        while True:
            audio_data = self.stream.read(self.CHUNK)[0]

            self.audio_buffer_deque.append(audio_data)
            # 专门用于计数
            if self.is_speech(audio_data):
                self.speech_history.append(1)
            else:
                self.speech_history.append(0)

            # print(self.speech_history.count(1),self.speech_history.count(0))
            # 如果状态是说话就一直填
            if self.say:
                # print(f'audio_data:{len(self.audio_buffer)}') # 打印阈值
                self.audio_buffer = np.append(self.audio_buffer, audio_data)
                print(self.audio_buffer.size)
                print(self.speech_history.count(0) >= self.MAX_QUEUE * 0.8)
                print(self.say)
                print(self.speech_history)

            if self.say == False and self.speech_history.count(1) > self.MAX_QUEUE * 0.7:
                await self.switch_state()
                print('检测到开始说话')
                audio_buffer_data = list(self.audio_buffer_deque)
                for audio_data in audio_buffer_data:
                    self.audio_buffer = np.append(self.audio_buffer, audio_data)

                # self.audio_buffer_deque.clear()

            if self.say == True and self.speech_history.count(0) >= self.MAX_QUEUE * 0.8 and self.audio_buffer.size > 0:
                await self.switch_state()
                print('检测到结束说话,开始识别')
                print(f'最低有效声音阈值：{self.VALID_AUDIO_THRESHOLD:.2f}')
                # print(len(self.audio_buffer))
                await self.transcribe_audio(self.audio_buffer)
                self.audio_buffer = np.array([])
                self.speech_history.clear()


            # self.audio_buffer_deque.clear()

    async def run(self):
        while True:
            try:
                async with websockets.connect(self.server_uri, ping_interval=20, ping_timeout=60,
                                              open_timeout=10) as websocket:
                    # await self.connect_to_server()

                    await self.listen_and_transcribe(websocket)
            except Exception as e:
                print(f'远程连接中断 抛出异常：{e} 尝试重新链接')
                await asyncio.sleep(1)


if __name__ == "__main__":
    # 如果类型没有就默认为Speech
    model_type=os.getenv('ASR_MODEL_TYPE',"Speech")
    recognizer = SpeechRecognizer(server_uri="ws://localhost:8765?name=ASR_Module",model_type=model_type)
    asyncio.run(recognizer.run())