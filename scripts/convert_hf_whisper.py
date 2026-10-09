"""Convert a HuggingFace transformers Whisper checkpoint to mlx-whisper format.

Usage: make model
   or: uv run python -m scripts.convert_hf_whisper <hf_repo_or_dir> <out_dir>
Key mapping follows ml-explore/mlx-examples whisper/convert.py.
"""

import json
import sys
from pathlib import Path

import mlx.core as mx
from huggingface_hub import snapshot_download

REPLACEMENTS = [
    ("model.", ""),
    (".layers", ".blocks"),
    (".self_attn", ".attn"),
    (".attn_layer_norm", ".attn_ln"),
    (".encoder_attn.", ".cross_attn."),
    (".encoder_attn_layer_norm", ".cross_attn_ln"),
    (".final_layer_norm", ".mlp_ln"),
    (".q_proj", ".query"),
    (".k_proj", ".key"),
    (".v_proj", ".value"),
    (".out_proj", ".out"),
    (".fc1", ".mlp1"),
    (".fc2", ".mlp2"),
    ("embed_positions.weight", "positional_embedding"),
    ("decoder.embed_tokens", "decoder.token_embedding"),
    ("encoder.layer_norm", "encoder.ln_post"),
    ("decoder.layer_norm", "decoder.ln"),
]


def remap(key: str) -> str:
    for old, new in REPLACEMENTS:
        key = key.replace(old, new)
    return key


def main(src: str, out: str):
    src_dir = Path(src) if Path(src).is_dir() else Path(snapshot_download(src, local_files_only=True))
    hf = json.loads((src_dir / "config.json").read_text())
    dims = {
        "n_mels": hf["num_mel_bins"],
        "n_audio_ctx": hf["max_source_positions"],
        "n_audio_state": hf["d_model"],
        "n_audio_head": hf["encoder_attention_heads"],
        "n_audio_layer": hf["encoder_layers"],
        "n_vocab": hf["vocab_size"],
        "n_text_ctx": hf["max_target_positions"],
        "n_text_state": hf["d_model"],
        "n_text_head": hf["decoder_attention_heads"],
        "n_text_layer": hf["decoder_layers"],
    }
    weights = {}
    for f in sorted(src_dir.glob("*.safetensors")):
        weights.update(mx.load(str(f)))
    weights.pop("proj_out.weight", None)  # tied to decoder token embedding
    converted = {}
    for k, v in weights.items():
        k = remap(k)
        if k == "encoder.positional_embedding":
            continue  # mlx-whisper computes sinusoids itself
        if "conv" in k and v.ndim == 3:
            v = v.swapaxes(1, 2)  # torch (out, in, k) -> mlx (out, k, in)
        converted[k] = v.astype(mx.float16)
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    mx.save_safetensors(str(out_dir / "weights.safetensors"), converted)
    (out_dir / "config.json").write_text(json.dumps(dims, indent=2))
    print(f"Wrote {len(converted)} tensors to {out_dir}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
