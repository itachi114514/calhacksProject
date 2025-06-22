import subprocess
import time
import os


def start_process(name, script, cwd, args=None, delay=1, log_dir="logs"):
    """
    启动一个子进程模块并将其输出重定向到日志文件
    :param name: 模块名（用于打印和日志文件名）
    :param script: 要运行的脚本文件
    :param cwd: 工作目录
    :param args: 参数列表
    :param delay: 启动后等待多少秒
    :param log_dir: 日志文件存放目录
    """
    command = ["python3", script] + (args or [])
    print(f"[启动中] {name} => {command} @ {cwd}")

    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)

    # 准备日志文件路径
    # 使用 'a' (追加模式) 而不是 'w' (写入模式)，这样重启脚本时不会覆盖旧日志
    # buffering=1 表示行缓冲，utf-8 编码
    stdout_log_path = os.path.join(log_dir, f"{name}_stdout.log")
    stderr_log_path = os.path.join(log_dir, f"{name}_stderr.log")

    stdout_file = open(stdout_log_path, "a", encoding="utf-8", buffering=1)
    stderr_file = open(stderr_log_path, "a", encoding="utf-8", buffering=1)

    print(f"  标准输出 -> {stdout_log_path}")
    print(f"  标准错误 -> {stderr_log_path}")

    # 启动子进程，重定向 stdout 和 stderr
    process = subprocess.Popen(command, cwd=cwd, stdout=stdout_file, stderr=stderr_file)
    time.sleep(delay)  # 启动后等待

    # 将文件句柄附加到进程对象上，以便在需要时可以显式关闭它们
    # (虽然 Popen 在其 __del__ 中通常会尝试关闭，但显式管理更好)
    process._custom_stdout_file = stdout_file
    process._custom_stderr_file = stderr_file
    return process


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_directory = os.path.join(base_dir, "process_logs")  # 统一的日志目录
    processes = []

    # 1. 启动 GPT-SoVITS
    processes.append(
        start_process(
            name="GPT_SoVITS",
            script="api_v2.py",
            cwd=os.path.join(base_dir, "gpt_sovits"),
            args=["-c", "./kelin/kelin.yaml"],
            log_dir=log_directory
        ))

    # 2. 启动服务器
    processes.append(
        start_process(
            name="Server",
            script="server.py",
            cwd=os.path.join(base_dir, "Server"),
            log_dir=log_directory
        ))

    # 3. 启动 ASR 模块
    processes.append(
        start_process(
            name="ASR_Module",
            script="asr_module.py",
            cwd=os.path.join(base_dir, "ASR_Module"),
            log_dir=log_directory
        ))

    # 4. 启动 LLM 模块
    processes.append(
        start_process(
            name="LLM_Module",
            script="llm_module.py",
            cwd=os.path.join(base_dir, "LLM_Module"),
            log_dir=log_directory
        ))

    # 5. 启动 Action 模块
    processes.append(
        start_process(
            name="Action_Module",
            script="action_module.py",
            cwd=os.path.join(base_dir, "Action_Module"),
            log_dir=log_directory
        ))

    # 6. 启动 TTS 模块
    processes.append(
        start_process(
            name="TTS_Module",
            script="tts_module.py",
            cwd=os.path.join(base_dir, "TTS_Module"),
            log_dir=log_directory
        ))

    # 7. 启动 Unity 通信模块
    processes.append(
        start_process(
            name="Unity_Module",
            script="unity_module.py",
            cwd=os.path.join(base_dir, "Unity_Module"),
            log_dir=log_directory
        ))

    # 8. 启动交互模块
    processes.append(
        start_process(
            name="Interaction_Module",
            script="interaction_module.py",
            cwd=os.path.join(base_dir, "Interaction_Module"),
            log_dir=log_directory
        ))

    print(f"\n✅ 所有模块已按顺序启动。日志输出到 '{log_directory}' 目录。")
    print("   你可以使用 'tail -f process_logs/模块名_stdout.log' 来实时查看特定模块的日志。")

    try:
        while True:
            # 可以选择性地检查进程是否仍在运行
            for p in processes:
                if p.poll() is not None:  # 进程已终止
                    print(f"⚠️ 进程 {p.args} (PID: {p.pid}) 已终止，返回码: {p.returncode}")
                    # 这里可以添加重新启动逻辑或将其从列表中移除
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n收到中断信号，终止所有子进程...")
        for p in processes:
            if p.poll() is None:  # 如果仍在运行
                print(f"  终止 {p.args} (PID: {p.pid})")
                p.terminate()  # 发送 SIGTERM

        # 等待进程终止
        for p in processes:
            try:
                p.wait(timeout=5)  # 等待最多5秒
            except subprocess.TimeoutExpired:
                print(f"  进程 {p.args} (PID: {p.pid}) 未在5秒内终止，强制结束...")
                p.kill()  # 发送 SIGKILL
            finally:
                # 关闭我们打开的日志文件
                if hasattr(p, '_custom_stdout_file') and p._custom_stdout_file:
                    p._custom_stdout_file.close()
                if hasattr(p, '_custom_stderr_file') and p._custom_stderr_file:
                    p._custom_stderr_file.close()
        print("所有子进程已处理。")