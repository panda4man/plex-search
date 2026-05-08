#!/usr/bin/env bash
set -e

ollama serve &
OLLAMA_PID=$!

echo "Waiting for Ollama server to be ready..."
until curl -sf http://localhost:11434/ > /dev/null 2>&1; do
  sleep 2
done
echo "Ollama server ready."

pull_if_missing() {
  local model="$1"
  if ollama list | grep -q "^${model}"; then
    echo "Model '${model}' already present, skipping pull."
  else
    echo "Pulling model: ${model}"
    ollama pull "${model}"
  fi
}

pull_if_missing "${OLLAMA_MODEL:-qwen2.5:7b}"
pull_if_missing "${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

echo "All models ready."
wait "$OLLAMA_PID"
