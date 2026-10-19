# Cleanup model

A small LLM fine-tuned for a single job: turning Roman-Hinglish dictation as spoken into what was
meant. It removes fillers and stutters and resolves self-corrections. It is not a general assistant.

```
Lisa ko call karo, nahi, Mary ko call karo   ->  Mary ko call karo
Monday ko meet karte hain, sorry, Wednesday ko  ->  Wednesday ko meet karte hain
main nahi aaunga                                ->  main nahi aaunga   (negation, left alone)
```

LocalFlow (`localflow/modules/cleanup/model.py`) runs it on MLX with two safeguards:

- **Gate:** it only sees text containing a cue word, a filler or a repeated word, so fluent dictation is
  pasted untouched.
- **Guard:** any output containing a word the speaker never said is rejected.

In both cases the deterministic rules in `rules.py` produce the result instead. Without a model in
`localflow/static/models/hinglish-cleanup-mlx`, only the rules run.

## Pipeline

```sh
make train-cleanup   # generate data, LoRA fine-tune, fuse into localflow/static/models/
make eval-cleanup ARGS="--valid"
```

1. **Data**, from `generate_data.py`:
   - Source: clean sentences from
     [findnitai/english-to-hinglish](https://huggingface.co/datasets/findnitai/english-to-hinglish)
     (Apache-2.0, 189k Roman-Hinglish sentences, mostly commands and chat). Download
     `hinglish_upload_v1.json` into `training/data/` first.
   - Each sentence is the target, and its input is a messy spoken version:
     - a day, number, name, place or noun said wrong and then corrected, in four shapes: inline, short
       repair, repeated clause, abandoned restart
     - stutters
     - fillers
   - About 35% of inputs must come out unchanged: negations, "…, nahi to …", a leading "Sorry,", an
     unrelated "…, actually …", and real reduplication ("jaldi jaldi").
   - Valid pairs use sentences the training set never sees.
2. **Fine-tune**, with `lora.yaml`: LoRA rank 16 on all layers of `Qwen2.5-0.5B-Instruct` (4-bit), loss
   on the completion only. It takes about an hour on an M2 Pro.
3. **Fuse** the adapter into the base model, about 280 MB.

## Evaluation

`localflow/static/eval/cleanup.tsv` holds hand-written cases, including traps: negations, "actually"
meaning "by the way", and "matlab" explaining rather than correcting. No sentence in it comes from the
training corpus.

`make eval-cleanup` reports accuracy, how many sentences were changed when they shouldn't have been, and
latency, for rules alone and for the model with rules as fallback.
