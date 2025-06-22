import cv2
import os
import argparse
import time
import face_recognition
from datetime import datetime


class FaceCollector:
    def __init__(self, output_dir, min_faces=1, max_faces=5, face_size_threshold=150):
        """初始化人脸采集系统

        Args:
            output_dir: 保存人脸图像的目录
            min_faces: 每个人至少采集的人脸数量
            max_faces: 每个人最多采集的人脸数量
            face_size_threshold: 人脸最小尺寸阈值(像素)，小于此值的人脸被忽略
        """
        self.output_dir = output_dir
        self.min_faces = min_faces
        self.max_faces = max_faces
        self.face_size_threshold = face_size_threshold

        # 确保输出目录存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"已创建输出目录: {output_dir}")

    def start_collection(self, camera_id=0):
        """启动人脸采集过程"""
        # 初始化摄像头
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            print(f"无法打开摄像头 ID: {camera_id}")
            return

        # 获取摄像头分辨率
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"摄像头分辨率: {width}x{height}")

        while True:
            # 输入人名
            person_name = input("\n请输入人名 (或输入'q'退出): ").strip()
            if person_name.lower() == 'q':
                break

            if not person_name:
                print("人名不能为空，请重新输入")
                continue

            # 为该用户创建子目录
            person_dir = os.path.join(self.output_dir, person_name)
            if not os.path.exists(person_dir):
                os.makedirs(person_dir)

            # 开始人脸采集过程
            self._collect_faces_for_person(cap, person_name, person_dir)

    def _collect_faces_for_person(self, cap, person_name, person_dir):
        """为特定人员采集人脸"""
        collected_count = 0
        frame_count = 0
        last_capture_time = 0

        print(f"\n开始为 {person_name} 采集人脸图像...")
        print(f"请看向摄像头，系统将自动采集 {self.min_faces}-{self.max_faces} 张人脸图像")
        print("采集过程中按 'q' 可以提前结束采集")

        # 检查目录中已有多少张人脸图像
        existing_files = [f for f in os.listdir(person_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
        if existing_files:
            print(f"注意: 目录中已存在 {len(existing_files)} 张图像")
            choice = input("是否继续添加图像? (y/n): ").strip().lower()
            if choice != 'y':
                return

        while collected_count < self.max_faces:
            ret, frame = cap.read()
            if not ret:
                print("无法获取视频帧")
                break

            frame_count += 1
            # 每3帧处理一次，减少CPU负担
            if frame_count % 3 != 0:
                # 显示实时画面但不处理
                display_frame = frame.copy()
                cv2.putText(display_frame, f"已采集: {collected_count}/{self.max_faces}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imshow('人脸采集', display_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            # 检测人脸
            rgb_frame = frame[:, :, ::-1]  # BGR转RGB
            face_locations = face_recognition.face_locations(rgb_frame)

            display_frame = frame.copy()

            # 检查是否检测到人脸
            if len(face_locations) == 1:  # 只处理单人场景
                # 获取当前时间
                current_time = time.time()
                # 确保每次捕获之间至少间隔1秒
                if current_time - last_capture_time >= 1.0:
                    top, right, bottom, left = face_locations[0]
                    face_width = right - left
                    face_height = bottom - top

                    # 检查人脸尺寸是否足够大
                    if face_width >= self.face_size_threshold and face_height >= self.face_size_threshold:
                        # 绘制绿色框表示合格的人脸
                        cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 255, 0), 2)

                        # 保存人脸图像
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"{person_name}_{timestamp}.jpg"
                        filepath = os.path.join(person_dir, filename)

                        # 裁剪并保存整个人脸，带有一些边距
                        margin = max(face_width, face_height) // 4
                        img_h, img_w = frame.shape[:2]

                        # 确保不超出图像边界
                        crop_top = max(0, top - margin)
                        crop_bottom = min(img_h, bottom + margin)
                        crop_left = max(0, left - margin)
                        crop_right = min(img_w, right + margin)

                        face_img = frame[crop_top:crop_bottom, crop_left:crop_right]
                        cv2.imwrite(filepath, face_img)

                        collected_count += 1
                        last_capture_time = current_time
                        print(f"已保存人脸图像 {collected_count}/{self.max_faces}: {filename}")
                    else:
                        # 绘制红色框表示人脸太小
                        cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 0, 255), 2)
                        cv2.putText(display_frame, "人脸太小", (left, top - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

            # 显示采集进度
            cv2.putText(display_frame, f"已采集: {collected_count}/{self.max_faces}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # 如果没有检测到人脸，显示提示
            if len(face_locations) == 0:
                cv2.putText(display_frame, "未检测到人脸", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            elif len(face_locations) > 1:
                cv2.putText(display_frame, "检测到多个人脸，请确保画面中只有一个人", (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow('人脸采集', display_frame)

            # 检查是否达到最小采集数量并询问是否继续
            if collected_count >= self.min_faces and collected_count % self.min_faces == 0:
                # 暂停视频显示但保持窗口
                print(f"\n已采集 {collected_count} 张人脸图像")
                choice = input("是否继续采集更多图像? (y/n): ").strip().lower()
                if choice != 'y':
                    break

            # 按q键退出当前人的采集
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        print(f"\n{person_name} 的人脸采集完成，共采集了 {collected_count} 张图像")

        # 显示采集结果预览
        self._show_collection_preview(person_dir)

    def _show_collection_preview(self, person_dir):
        """显示采集结果预览"""
        files = [f for f in os.listdir(person_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
        if not files:
            return

        print("\n采集结果预览:")

        # 最多显示6张图像
        preview_count = min(6, len(files))
        images = []

        for i in range(preview_count):
            img_path = os.path.join(person_dir, files[i])
            img = cv2.imread(img_path)
            if img is not None:
                # 调整图像大小以便于显示
                img = cv2.resize(img, (200, 200))
                images.append(img)

        # 创建预览网格
        rows = (preview_count + 2) // 3  # 每行最多3张图
        cols = min(3, preview_count)

        preview = None
        idx = 0

        for r in range(rows):
            row_images = []
            for c in range(cols):
                if idx < len(images):
                    row_images.append(images[idx])
                    idx += 1
                else:
                    # 使用空白图像填充
                    row_images.append(np.zeros((200, 200, 3), dtype=np.uint8))

            # 水平连接这一行的图像
            row = np.hstack(row_images)

            # 垂直连接行
            if preview is None:
                preview = row
            else:
                preview = np.vstack((preview, row))

        # 显示预览
        cv2.imshow('采集结果预览', preview)
        print("请查看采集结果预览窗口，按任意键继续...")
        cv2.waitKey(0)
        cv2.destroyWindow('采集结果预览')


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='人脸采集程序')
    parser.add_argument('--output', default='known_faces', help='保存人脸图像的目录')
    parser.add_argument('--min', type=int, default=1, help='每人最少采集的人脸数量')
    parser.add_argument('--max', type=int, default=5, help='每人最多采集的人脸数量')
    parser.add_argument('--size', type=int, default=150, help='人脸最小尺寸阈值(像素)')
    parser.add_argument('--camera', type=int, default=0, help='摄像头ID（默认为0）')

    args = parser.parse_args()

    print("\n===== 人脸采集程序 =====")
    print(f"输出目录: {args.output}")
    print(f"每人采集数量: {args.min}-{args.max}")
    print(f"人脸最小尺寸阈值: {args.size}像素")
    print(f"摄像头ID: {args.camera}")
    print("=========================\n")

    collector = FaceCollector(args.output, args.min, args.max, args.size)
    collector.start_collection(args.camera)

    print("\n人脸采集程序已结束")
    cv2.destroyAllWindows()


if __name__ == "__main__":
    import numpy as np  # 导入numpy用于图像处理

    main()