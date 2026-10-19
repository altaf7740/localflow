.PHONY: help install model start stop status restart web eval test lint lint-fix check clean

WHISPER_HF := Oriserve/Whisper-Hindi2Hinglish-Apex
WHISPER_MLX := localflow/static/models/whisper-hindi2hinglish-apex-mlx
CLEANUP_MODEL := qwen2.5:7b-instruct
# this repo's interpreter only, so another checkout of LocalFlow keeps running
APP_PROCESS := $(CURDIR)/.venv/bin/python.* -m localflow.main

# Colors
C := \033[36m
G := \033[32m
Y := \033[33m
R := \033[0m

help:
	@echo "$(Y)Usage:$(R) make [target]\n"
	@echo "$(C)Setup:$(R)"
	@echo "  $(G)install$(R)      Install dependencies (incl. dev tools)"
	@echo "  $(G)model$(R)        Convert Hinglish Whisper to MLX (Apple Silicon), else pull the Ollama cleanup model"
	@echo ""
	@echo "$(C)App:$(R)"
	@echo "  $(G)start$(R)        Run LocalFlow (menu bar on macOS, tray on Windows/Linux)"
	@echo "  $(G)stop$(R)         Stop a running LocalFlow"
	@echo "  $(G)status$(R)       Check if LocalFlow is running"
	@echo "  $(G)restart$(R)      Stop, then start"
	@echo "  $(G)web$(R)          Dictate over HTTP + test page at http://localhost:8766 [HOST= PORT= CORS=]"
	@echo ""
	@echo "$(C)Evaluation:$(R)"
	@echo "  $(G)eval$(R)         Score WER + latency on localflow/static/eval (ARGS=\"--asr <dir>[:lang] --llm <model>\")"
	@echo ""
	@echo "$(C)Testing & Code Quality:$(R)"
	@echo "  $(G)test$(R)         Run tests"
	@echo "  $(G)lint$(R)         Show linting errors"
	@echo "  $(G)lint-fix$(R)     Fix linting errors and format"
	@echo "  $(G)check$(R)        Lint, format, and test"
	@echo ""
	@echo "$(C)Cleanup:$(R)"
	@echo "  $(G)clean$(R)        Remove cache files"

install:
	uv sync --all-groups

model:
ifeq ($(shell uname -s)-$(shell uname -m),Darwin-arm64)
	@test -f $(WHISPER_MLX)/weights.safetensors && echo "MLX Whisper already at $(WHISPER_MLX)" \
		|| uv run python -m scripts.convert_hf_whisper $(WHISPER_HF) $(WHISPER_MLX)
else
	ollama pull $(CLEANUP_MODEL)
endif

start:
	uv run python -m localflow.main

stop:
	@pkill -f "$(APP_PROCESS)" 2>/dev/null && echo "LocalFlow stopped" || echo "LocalFlow not running"

status:
	@pgrep -f "$(APP_PROCESS)" > /dev/null && echo "LocalFlow is running" || echo "LocalFlow is NOT running"

restart: stop start

web:
	uv run python -m scripts.web $(if $(HOST),--host $(HOST)) $(if $(PORT),--port $(PORT)) $(if $(CORS),--cors $(foreach o,$(CORS),'$(o)'))

eval:
	uv run python -m scripts.run_eval $(ARGS)

test:
	uv run pytest

lint:
	uv run ruff check

lint-fix:
	uv run ruff check --fix
	uv run ruff format

check: lint-fix test

clean:
	find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
