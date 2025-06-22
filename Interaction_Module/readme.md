# 主动交互模块（Face + Pose Tracking）

该模块通过摄像头实时获取画面，识别已知人脸并估计头部姿态。当检测到人员正面注视时，向 WebSocket 服务发送身份信息，可用于交互式应用（如虚拟角色唤醒等场景）。


---

## 🌟 功能说明

- 人脸识别：支持多张照片构建数据库、支持未知人脸过滤
- 姿态估计：基于 MediaPipe 进行头部姿态估计并转换为 Pitch、Yaw、Roll
- WebSocket 通信：识别出人脸正对摄像头时发送身份消息（带频率限制）
- 摄像头标定：使用 OpenCV `solvePnP` 获取真实空间位置，确保姿态精准
- 支持双模块协作：统一和语音模块共享数据协议（`DATA:<name>`）

---

## 🔧 使用方法

1. 采集已知人脸照片：

   ```bash
   python tools/getface.py
   ```

   > 会在 `./known_faces/<person_name>/` 生成多张照片用于识别。

2. 进行摄像头标定（生成 `calibration.npz`）：

   ```bash
   python tools/CameraCalibrate.py
   ```

3. 运行主程序：

   ```bash
   python interaction_module.py
   ```

   > 默认使用 `ws://localhost:8770?name=Interaction_Module` 与其他模块通信。

---

## ⚙️ 配置说明

| 配置项              | 描述                                      |
|---------------------|-------------------------------------------|
| `./known_faces/`    | 已知人脸数据目录，每个子目录名为人名        |
| `calibration.npz`   | 相机内参文件，含 `camera_matrix` 和 `dist_coefficients` |
| `mediapipe landmarks` | 使用的六个关键点索引：[1, 152, 33, 263, 61, 291] |

---
