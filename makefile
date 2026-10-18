.PHONY: help install model start stop status restart eval test lint lint-fix check clean

WHISPER_HF := openai/whisper-large-v3-turbo
WHISPER_MLX := localflow/static/models/whisper-large-v3-turbo-mlx
CLEANUP_MODEL := qwen2.5:7b-instruct

# Colors
C := \033[36m
G := \033[32m
Y := \033[33m
R := \033[0m

help:
	@echo "$(Y)Usage:$(R) make [target]\n"
	@echo "$(C)Setup:$(R)"
	@echo "  $(G)install$(R)      Install dependencies (incl. dev tools)"
	@echo "  $(G)model$(R)        Convert Whisper to MLX (Apple Silicon) and pull the Ollama cleanup model"
	@echo ""
	@echo "$(C)App:$(R)"
	@echo "  $(G)start$(R)        Run LocalFlow (menu bar on macOS, tray on Windows/Linux)"
	@echo "  $(G)stop$(R)         Stop a running LocalFlow"
	@echo "  $(G)status$(R)       Check if LocalFlow is running"
	@echo "  $(G)restart$(R)      Stop, then start"
	@echo ""
	@echo "$(C)Evaluation:$(R)"
	@echo "  $(G)eval$(R)         Score ASR + cleanup on localflow/static/eval (ARGS=\"--no-cleanup --llm <model>\")"
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
endif
	ollama pull $(CLEANUP_MODEL)

start:
	uv run python -m localflow.main

stop:
	@pkill -f "python -m localflow.main" 2>/dev/null && echo "LocalFlow stopped" || echo "LocalFlow not running"

status:
	@pgrep -f "python -m localflow.main" > /dev/null && echo "LocalFlow is running" || echo "LocalFlow is NOT running"

restart: stop start

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
