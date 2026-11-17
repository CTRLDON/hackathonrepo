#!/usr/bin/env bash
set -e

HOST_URL="${OLLAMA_HOST:-http://ollama:11434}"
MODEL="${OLLAMA_MODEL:-qwen2.5-coder:7b}"

# Download the model in the background so the web UI is reachable immediately.
# Until the download finishes, the UI shows "model still downloading" instead of the page
# being unreachable (first run is ~4.7 GB).
(
  for i in $(seq 1 60); do
    curl -sf "${HOST_URL}/api/tags" >/dev/null 2>&1 && break
    sleep 2
  done
  echo "[entrypoint] Pulling ${MODEL} in the background (first run ~4.7 GB)..."
  if curl -sf -X POST "${HOST_URL}/api/pull" -H 'Content-Type: application/json' \
       -d "{\"name\":\"${MODEL}\",\"stream\":false}" >/dev/null; then
    echo "[entrypoint] Model ${MODEL} ready."
  else
    echo "[entrypoint] Model pull failed; run: docker compose exec ollama ollama pull ${MODEL}"
  fi
) &

echo "[entrypoint] Starting app on ${HOST:-0.0.0.0}:${PORT:-8000} (open http://localhost:${PORT:-8000})..."
exec python main.py
