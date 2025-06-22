# ASR 模块

该模块监听麦克风输入，使用 FunASR 模型进行语音识别，并通过 WebSocket 将识别结果实时发送给服务端。支持声纹识别、状态切换控制，并使用 WebRTC VAD 进行静音检测。

---

## 🌟 功能说明

- 实时语音识别（中文）
- 使用 WebRTC VAD 进行静音检测
- 自动控制说话状态开关（通过 `SWITCH_STATE`）
- 声纹匹配并发送说话人文本内容
- 可选文字输入测试模式（用于调试）

---

## 🔧 使用方法

1. 准备模型目录：

   ```
   src/SenseVoiceSmall/
   ```

   或可切换为：

   ```
   src/paraformer-zh/
   ```

2. 准备说话人特征文件：

   ```
   src/embedding.pkl
   ```

   > 内含 `spk_embedding`，用于计算相似度（目前采用 CosineSimilarity）

3. 启动识别模块：

   ```bash
   python asr_stream.py
   ```

   > 默认连接地址为 `ws://localhost:8765?name=ASR_Module`

---

## ⚙️ 配置说明

| 配置项               | 描述                                        |
|----------------------|---------------------------------------------|
| `model_path`         | 使用的 FunASR 模型路径（默认为 `SenseVoiceSmall`） |
| `DEVICE`             | 麦克风设备编号（可用 `sd.query_devices()` 查看）    |
| `embedding.pkl`      | 预存的说话人特征向量，此文件用于存储说话人特征向量。当前保存的是BIN的           |
| `SWITCH_STATE` 消息  | 用于通知服务端当前是否处于“说话”状态              |

---

## 🧪 测试

可启用文字输入替代语音：

取消85行注释 
   ```bash
    await self.test()
   ```
---

- ~~**重要修改**：请手动删除 `funasr/auto/auto_model.py` 文件中的第 621 和 622 行，否则部分模型会出错~~
- WebSocket 通信采用状态同步机制：
- 本模块发送 `"SWITCH_STATE"`，服务端根据语境决定广播 `"SAY:true"` 或 `"SAY:false"` 给其他模块

