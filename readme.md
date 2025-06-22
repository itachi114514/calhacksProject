# Hikari Mirror
*also readme for server.py*

TODO:
* Overall(`Server.py`)

   - [x] 为每个模块添加readme
   - [x] 将mubai最新的改动合并进来
   - [ ] 模块看门狗+重连
   - [x] ~~写一个启动所有模块的主入口~~ 写`.sh🍥` 和 `.bat`
   - [ ] 弃用funasr

* ASR_Module

   - [x] 声纹识别
   - [x] 更新中间件及统一传输协议
   - [x] 修复语音识别bug
   - [ ] 使用小模型判断对话是否延续
   
* Interaction_Module

   - [x] 人脸识别
   - [x] 头部姿态估计
   - [x] WebSocket 消息交互
   - [x] 更新统一数据协议
   - [ ] 增加行为识别（如眨眼、张嘴）
   - [ ] 多人姿态关联（谁在正对摄像头）
   - [ ] 集成语音唤醒（与 TTS 模块联动）

* LLM_Module

   - [x] 角色人格注入（胡桃设定）
   - [x] 支持打断生成
   - [x] 增量句子输出（含终止符判断）
   - [ ] 多角色切换支持（如钟离、可莉）
   - [ ] 增强情绪识别与应答调整 [half]
   - [ ] 接入视觉/听觉环境输入（如 `ENV:`/`PEO:`）[half]

* TTS_Module

   - [x] 流式音频数据发送
   - [x] 语音请求
   - [x] 打断功能

* Unity_Module

   - [x] 基于 buffer 的音频转发逻辑
   - [x] 支持动作指令 `SWITCH_ACTION` 随机切换
   - [x] 接收中断指令 `SAY:false` 并清空缓冲区
   - [ ] `audio_buffer` 使用 `bytearray` 管理，谨防溢出。(?)
   - [ ] `SWITCH_ACTION`与交谈内容相关的动作调用，先用提示词注入实现。*已经实现了，只需要整合*
   - [ ] 与大飞老师的excel对齐一下 `@addone`

* gpt_sovits

    - [ ] 更新到v3以解决LangSegment最高支持为0.2.0的问题

## 模块介绍
1. **ASR_Module** (`port: 8765`)
   - 接收音频数据并转换为文本。
   - 通过VoiceID进行声纹识别。
   - 使用VAD进行语音活动检测并判断打断SAY:。
   - 转发文本数据到 `LLM_Module`。
   
2. **LLM_Module** (`port: 8766`)
   - 接收文本数据并生成回答。
   - 转发文本数据到 `TTS_Module`。

3. **Unity_Module** (`port: 8767`)
   - 接收音频数据（由 `TTS_Module` 转发），并执行相关动作。
   
4. **TTS_Module** (`port: 8768`)
   - 接收文本数据并将其转换为语音。
   - 将生成的音频数据传送给 `Unity_Module`。

5. **Interaction_Module** (`port: 8770`)
   - 接收指令，触发 `LLM_Module` 生成回答。

6. **gpt_sovits** (`port: 9880`)
   - 用于语音合成，接收文本并生成对应的音频。与 `TTS_Module` 协同工作。
    
### 模块之间的通信流程：
1. `ASR_Module` 通过 WebSocket 接收音频数据，转换为文本并转发到 `LLM_Module`。
2. `LLM_Module` 生成文本回答并将其传递到 `TTS_Module`。
3. `TTS_Module` 转换文本为音频并通过 WebSocket 转发给 `Unity_Module`。
4. `Unity_Module` 播放接收到的音频与发送动作。
5. `Interaction_Module` 接收命令并触发 `LLM_Module` 生成相应的回答。

### 系统状态管理：
- `SAY:bool`: 全局打断符。
- `generating:bool`: 音频生成状态。
~~- `audio_end`: 目前没有用法。不用管。  LLM module生成的时候会阻塞，用这个状态标志生成完成，被`generating:bool`取代了~~


