#!/bin/bash

# 脚本所在目录
BASE_DIR=$(dirname "$(realpath "$0")")
cd "$BASE_DIR" || exit 1

# Tmux 会话名称
SESSION_NAME="app_log_monitor_single_window_v5" # 再换个名测试
# 日志目录
LOG_DIR="${BASE_DIR}/process_logs"

# 模块定义
MODULE_NAMES=(
    "GPT_SoVITS"
    "Server"
    "ASR_Module"
    "LLM_Module"
    "Action_Module"
    "TTS_Module"
    "Unity_Module"
    "Interaction_Module"
    "Agent_Module"
)

# 检查 tmux 是否安装
if ! command -v tmux &> /dev/null; then echo "错误: tmux 未安装."; exit 1; fi
# 检查日志目录
if [ ! -d "$LOG_DIR" ]; then echo "警告: 日志目录 '$LOG_DIR' 不存在。"; fi

start_tmux_monitor() {
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        read -r -p "Tmux 会话 '$SESSION_NAME' 已存在。附加 (a) 或 重启 (r)? [a/r]: " choice
        case "$choice" in
            r|R ) tmux kill-session -t "$SESSION_NAME"; sleep 0.5 ;;
            a|A|* ) tmux attach-session -t "$SESSION_NAME"; exit 0 ;;
        esac
    fi

    echo "正在创建新的 tmux 会话 '$SESSION_NAME' (单窗口，多窗格)..."

    # 1. 创建会话和第一个窗口
    tmux new-session -d -s "$SESSION_NAME" -n "All_Logs"
    local window_target_identifier="$SESSION_NAME:All_Logs" # 窗口的标识符

    local pane_count=0
    for module_name in "${MODULE_NAMES[@]}"; do
        local stdout_log="${LOG_DIR}/${module_name}_stdout.log"
        touch "$stdout_log"
        local cmd_to_run="echo \"Monitoring ${module_name} (stdout)\"; tail -n 2 -f \"${stdout_log}\""

        if [ $pane_count -eq 0 ]; then
            # 第一个模块，命令发送到新会话的第一个窗口的默认窗格
            # 此时这个窗格是活动的
            tmux send-keys -t "$window_target_identifier" "$cmd_to_run" C-m # 省略 .0, tmux 会发给活动窗格
        else
            # 对于后续模块:
            # 1. 分割当前窗口的活动窗格 (split-window 默认行为)
            #    -h 水平分割，新窗格在右边
            #    新创建的窗格会自动成为活动窗格
            tmux split-window -h # 你可以改成 -v
            
            # 2. 向新的活动窗格发送命令
            #    同样，省略 -t，tmux 会发给当前活动窗格
            tmux send-keys "$cmd_to_run" C-m
        fi
        
        # 每次操作后，重新应用 tiled 布局到当前窗口
        tmux select-layout -t "$window_target_identifier" tiled
        
        pane_count=$((pane_count + 1))
        sleep 0.3 # 稍微增加延迟以确保命令执行顺序
    done

    echo "Tmux 会话 '$SESSION_NAME' 已启动。"
    tmux attach-session -t "$SESSION_NAME"
}

# ... (stop_tmux_monitor 和主逻辑 case 与之前相同) ...
stop_tmux_monitor() {
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "正在终止 tmux 日志监控会话 '$SESSION_NAME'..."
        tmux kill-session -t "$SESSION_NAME"
        echo "Tmux 会话 '$SESSION_NAME' 已终止."
    else
        echo "Tmux 会话 '$SESSION_NAME' 未运行."
    fi
}

# 主逻辑
case "$1" in
    start)
        start_tmux_monitor
        ;;
    stop)
        stop_tmux_monitor
        ;;
    attach)
        if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
            tmux attach-session -t "$SESSION_NAME"
        else
            echo "Tmux 会话 '$SESSION_NAME' 未运行。正在尝试启动..."
            start_tmux_monitor
        fi
        ;;
    *)
        if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
            echo "发现现有会话 '$SESSION_NAME'，正在附加..."
            tmux attach-session -t "$SESSION_NAME"
        else
            echo "未发现会话 '$SESSION_NAME'，正在创建新的监控会话..."
            start_tmux_monitor
        fi
        ;;
esac
