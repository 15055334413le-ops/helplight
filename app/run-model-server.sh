#!/bin/bash
export PATH=$HOME/ollama-0.40.9/bin:$PATH
# 启动 Spark-X2.6-4B 推理服务（Ollama，OpenAI 兼容接口 http://127.0.0.1:11434/v1）
# 注意：本机出网走运行时 egress 代理，ollama 必须继承当前 shell 的 *_proxy 环境变量才能拉取模型，
# 因此不要用 systemd 的 ollama.service（不带代理 env），用本脚本启动。
pkill -x ollama 2>/dev/null; sleep 1
nohup ollama serve > ~/workspace/spark-her/logs/ollama-serve.log 2>&1 &
echo "ollama serve started, pid $!"
