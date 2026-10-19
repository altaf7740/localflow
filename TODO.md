# Handoff: Hinglish cleanup model (branch `hinglish-cleanup-model`)

Context for the next Claude Code session: read this first. Last updated 2026-10-19.

## Goal

Dictation pipeline that is **fast, accurate, light and Hinglish-native, without a general-purpose LLM**.
The user rejects Ollama/llama-style general LLMs for cleanup. They want deterministic rules or a **small
model trained only for this task**. They have 8× 32 GB CUDA GPUs for training. Inference runs on an
M2 Pro (16 GB).

## Done (committed on this branch)

1. **ASR switched** to Oriserve Whisper-Hindi2Hinglish-Apex on Apple Silicon:
   - Uses `language="en"` (`"hi"` breaks its Roman output) and keeps the Hinglish `asr_prompt`.
   - It writes Roman Hinglish directly, so the Ollama transliteration pass is off on Mac.
   - Windows/Linux are unchanged (stock turbo + Ollama), because no CTranslate2 build of Apex exists.
   - Bundled clips: WER 0.048 at 0.63 s/clip, vs 0.055 at 1.27 s/clip for turbo + Qwen 3B. The clips are
     synthetic and fluent.
2. **Empty-prompt fix:** `""` became a lone space token in mlx_whisper and wrecked decoding, so it's now
   passed as `None`.
3. **Rules** (`localflow/modules/cleanup/rules.py`):
   - Remove fillers (um/uh/hmm).
   - Day/number swaps ("kal nahin parso" → "parso").
   - Repair alignment: the repair echoes the stretch it replaces, which gets swapped.
   - If nothing aligns, the text is left as spoken.
   - 34/36 on `localflow/static/eval/cleanup.tsv`, 0 wrongly changed.
4. **Cleanup model scaffolding:**
   - `training/generate_data.py`: synthetic messy→clean pairs from findnitai/english-to-hinglish.
   - `training/lora.yaml`: mlx-lm LoRA on Qwen2.5-0.5B-Instruct-4bit.
   - `localflow/modules/cleanup/model.py`: gate + no-new-words guard, with rules as fallback.
   - `scripts/eval_cleanup.py`: `make eval-cleanup` compares rules vs model.
   - `make train-cleanup` does download → generate → train → fuse.
   - See `training/README.md`.

## In progress when handed off

- A pilot LoRA run on the M2 Pro (MLX):
  - At lr **2e-4** it diverged right after warmup (loss 0.3 → 7.4).
  - At **5e-5** it is stable (loss 0.016 at step 250 of 2000), but it was not finished.
- Checkpoints and data are gitignored. Rerun `make train-cleanup`; it's reproducible with seed 0.

## Next steps

1. **Finish a training run.**
   - **Office machine is Apple Silicon:** `make install && make train-cleanup`. That also fuses into
     `localflow/static/models/hinglish-cleanup-mlx`.
   - **Office machine is Linux/CUDA:** MLX doesn't run there. Write `training/train_gpu.py` with
     transformers + peft (or TRL SFT):
     - Same `train.jsonl`/`valid.jsonl` (`prompt`/`completion`) and chat template.
     - Loss on the completion only.
     - Base `Qwen/Qwen2.5-0.5B-Instruct` (bf16).
     - Then on the Mac: `mlx_lm.convert --hf-path <merged> -q` into `localflow/static/models/hinglish-cleanup-mlx`.
2. **Evaluate:** run `make eval-cleanup ARGS="--valid"`. The model must beat the rules (34/36, 0 wrongly
   changed) on `cleanup.tsv` and keep negations intact. Check p50/p90 latency; the target is under 100 ms.
3. If it wins, **shrink it**, re-evaluating after each step:
   - trim the vocabulary to Roman, digits, punctuation and some Devanagari (151k → ~30–65k tokens;
     tidy-1 did 65k)
   - drop layers (24 → 16 → 12) and re-fine-tune
   - quantize to 4-bit
4. **Data quality,** if the model is weak:
   - Add DISCO Hindi (github.com/vineet2104/DISCO, ~3.2k human pairs, Devanagari, so romanize it). Its
     license isn't stated, so check it first.
   - Have a large teacher on the GPUs (e.g. Qwen2.5-72B via vLLM) write and verify more natural
     corrections.
5. **Real data:**
   - The user should record 15–20 real clips (with fillers and self-corrections) into
     `localflow/static/eval/clips/` + `references.tsv`. The current 4 are synthetic "Lekha" voice.
   - Add real misses to `cleanup.tsv`.
6. **README:** document the cleanup model in the Pipeline section once it ships.
7. Then open a PR from `hinglish-cleanup-model`.

## Gotchas

- `qwen2.5:7b-instruct` was never pulled on the Mac, so the old LLM cleanup silently fell back to raw text.
- HF downloads can stall at 0 bytes (xet); use `HF_HUB_DISABLE_XET=1`.
- "matlab" is deliberately **not** a correction cue ("kal tak, matlab parso tak" explains, it doesn't
  correct). Generator, rules and eval agree on this.
- Bare "do" is usually the verb ("bhej do"), so the rules only treat it as the number two before a unit.
- Reference projects:
  - **tidy-1-mlx** (EnConvo): the same recipe for zh/en dictation cleanup, 86 ms on an M2.
  - **CapsWriter-Offline:** a similar hold-to-talk app.
  - AirLLM was judged not useful (too slow).
