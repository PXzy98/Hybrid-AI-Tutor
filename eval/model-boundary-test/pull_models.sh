#!/usr/bin/env bash
# Run on the Ollama server (192.168.2.25). Pass "all" to include the optional models.
REQUIRED="qwen3.5:2b qwen3.5:4b qwen3.5:9b qwen3.5:27b gemma4:e4b gemma4:12b gemma4:26b"
OPTIONAL="qwen3.5:0.8b gemma4:e2b gemma4:31b qwen3.8:27b qwen3.5:35b"
MODELS="$REQUIRED"; [ "$1" = "all" ] && MODELS="$REQUIRED $OPTIONAL"
for m in $MODELS; do echo "== $m"; ollama pull "$m" || echo "!! failed: $m (check the tag on ollama.com/library)"; done
ollama list
