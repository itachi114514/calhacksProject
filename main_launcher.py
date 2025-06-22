# file: main_launcher.py
import subprocess
import time
import os
import signal # 用于更优雅地处理信号

# 全局进程列表，以便信号处理器可以访问
processes_to_terminate = []
original_sigint_handler = signal.getsignal(signal.SIGINT)

def signal_handler(sig, frame):
    print("\n[主启动器] 收到中断信号，终止所有子进程...")
    global processes_to_terminate
    for p_info in reversed(processes_to_terminate): # 反向终止，可能更优雅
        p = p_info['process']
        name = p_info['name']
        if p.poll() is None: # 如果仍在运行
            print(f"  终止 {name} (PID: {p.pid})")
            p.terminate()

    # 等待进程终止
    for p_info in processes_to_terminate:
        p = p_info['process']
        name = p_info['name']
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"  进程 {name} (PID: {p.pid}) 未在5秒内终止，强制结束...")
            p.kill()
        finally:
            # 关闭我们打开的日志文件
            if hasattr(p, '_custom_stdout_file') and p._custom_stdout_file:
                try:
                    p._custom_stdout_file.close()
                except Exception as e:
                    print(f"关闭 {name} stdout 文件句柄失败: {e}")
            if hasattr(p, '_custom_stderr_file') and p._custom_stderr_file:
                try:
                    p._custom_stderr_file.close()
                except Exception as e:
                    print(f"关闭 {name} stderr 文件句柄失败: {e}")
    print("[主启动器] 所有子进程已处理。正在退出...")
    # 恢复原始SIGINT处理程序并重新引发信号，以便Python解释器可以正常退出
    signal.signal(signal.SIGINT, original_sigint_handler)
    # os.kill(os.getpid(), signal.SIGINT) # 这会导致脚本再次捕获SIGINT
    exit(0) #直接退出

def start_process(name, script, cwd, args=None, delay=0.2, log_dir="logs"):
    command = ["python3", script] + (args or [])
    print(f"[启动中] {name} => {command} @ {cwd}")
    os.makedirs(log_dir, exist_ok=True)

    stdout_log_path = os.path.join(log_dir, f"{name}_stdout.log")
    stderr_log_path = os.path.join(log_dir, f"{name}_stderr.log")

    # 'w' 模式在每次启动时清空日志，方便调试。如果需要追加，请用 'a'
    stdout_file = open(stdout_log_path, "w", encoding="utf-8", buffering=1)
    stderr_file = open(stderr_log_path, "w", encoding="utf-8", buffering=1)

    print(f"  标准输出 -> {stdout_log_path}")
    print(f"  标准错误 -> {stderr_log_path}")

    process = subprocess.Popen(command, cwd=cwd, stdout=stdout_file, stderr=stderr_file)
    time.sleep(delay)

    process._custom_stdout_file = stdout_file
    process._custom_stderr_file = stderr_file
    return process

if __name__ == "__main__":
    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_directory = os.path.join(base_dir, "process_logs")

    module_definitions = [
        {"name": "GPT_SoVITS", "script": "api_v2.py", "cwd_suffix": "gpt_sovits", "args": ["-c", "./kelin/kelin.yaml"]},
        {"name": "Server", "script": "server.py", "cwd_suffix": "Server"},
        {"name": "ASR_Module", "script": "asr_module.py", "cwd_suffix": "ASR_Module"},
        {"name": "LLM_Module", "script": "llm_module.py", "cwd_suffix": "LLM_Module"},
        {"name": "Action_Module", "script": "action_module.py", "cwd_suffix": "Action_Module"},
        {"name": "TTS_Module", "script": "tts_module.py", "cwd_suffix": "TTS_Module"},
        {"name": "Unity_Module", "script": "unity_module.py", "cwd_suffix": "Unity_Module"},
        # {"name": "Interaction_Module", "script": "interaction_module.py", "cwd_suffix": "Interaction_Module"},
        {"name": "Agent_Module", "script": "agent_module.py", "cwd_suffix": "Agent_Module"},
    ]

    print(f"日志将输出到: {log_directory}")
    # 启动前可选：清空旧的日志目录内容
    import shutil
    if os.path.exists(log_directory):
        shutil.rmtree(log_directory)
    os.makedirs(log_directory, exist_ok=True)


    for module_info in module_definitions:
        p = start_process(
            name=module_info["name"],
            script=module_info["script"],
            cwd=os.path.join(base_dir, module_info["cwd_suffix"]),
            args=module_info.get("args"),
            log_dir=log_directory
        )
        processes_to_terminate.append({"name": module_info["name"], "process": p})

    print("\n✅ 所有模块已按顺序启动。按 Ctrl+C 退出并终止所有模块。")

    try:
        while True:
            all_stopped = True
            for p_info in processes_to_terminate:
                if p_info['process'].poll() is None:
                    all_stopped = False
                    break
                else:
                    print(f"检测到模块 {p_info['name']} 已停止 (返回码: {p_info['process'].returncode})。")
                    # 可以选择从 processes_to_terminate 移除已停止的进程或尝试重启
            if all_stopped:
                print("所有子进程已意外停止。主启动器退出。")
                break
            time.sleep(5)
    except Exception as e: # 捕获除了KeyboardInterrupt之外的异常
        print(f"主循环发生错误: {e}")
    finally:
        # 确保在任何情况下（除了直接被kill -9）都会尝试清理
        if any(p_info['process'].poll() is None for p_info in processes_to_terminate):
             signal_handler(signal.SIGINT, None) # 手动调用清理