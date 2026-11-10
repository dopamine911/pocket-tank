"""A trained checkpoint read the way the device reads it (common/llm/advisor_core.c): BOS, the state
line's words and `->`, then a softmax over the goal tokens only (all the fish's eight, flee_shadow
included: the device takes every goal word in the vocabulary), at temperature 1.0 by default.

From dopamine911/pocket-terrarium model/probe_l1.py (class Student), reviewed and made fish-only
(issue #1). Needs torch and llama2.c/model.py (karpathy/llama2.c, see docs/pipeline.md).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_traces as gt  # noqa: E402
import train_tokenizer as tok  # noqa: E402

BATCH = 256


class Student:
    """train.py's checkpoint as the device runs it: the goal distribution after `<state> ->`"""

    def __init__(self, ckpt, temp=1.0, device="cpu", goals=None, name="fish v4"):
        import torch
        sys.path.insert(0, os.path.join(HERE, "llama2.c"))
        from model import ModelArgs, Transformer
        self.torch, self.temp = torch, temp
        self.goals, self.name = list(goals or gt.GOALS), name
        d = torch.load(ckpt, map_location="cpu")
        args = ModelArgs(**d["model_args"])
        if args.vocab_size != tok.VOCAB_SIZE:
            sys.exit(f"{ckpt}: vocab {args.vocab_size}, the {name} lexicon has {tok.VOCAB_SIZE}: not a {name} checkpoint")
        self.model = Transformer(args)
        state = {k[len("_orig_mod."):] if k.startswith("_orig_mod.") else k: v for k, v in d["model"].items()}
        self.model.load_state_dict(state, strict=True)
        self.model.to(device).eval()
        self.device = device
        self.max_seq_len = args.max_seq_len
        self.gid = [tok.encode(g)[0] for g in self.goals]
        self.info = {"iter": d.get("iter"), "val_loss": d.get("val_loss"), "goal_nll": d.get("goal_nll"),
                     "loss": d.get("loss"), "model_args": d["model_args"]}

    def dists(self, lines):
        """[({goal: p}, goal-token mass)] for each line; lines of one token length go as one batch"""
        torch = self.torch
        ids = [tok.encode(line + " ->", bos=True) for line in lines]
        by_len = {}
        for i, s in enumerate(ids):
            if tok.UNK_ID in s or len(s) > self.max_seq_len:
                sys.exit(f"not a {self.name} line the model can read: {lines[i]!r}")
            by_len.setdefault(len(s), []).append(i)
        out = [None] * len(lines)
        with torch.no_grad():
            for idx in by_len.values():
                for k in range(0, len(idx), BATCH):
                    chunk = idx[k:k + BATCH]
                    logits = self.model(torch.tensor([ids[i] for i in chunk], dtype=torch.long, device=self.device))[:, -1, :]
                    p = torch.softmax(logits[:, self.gid] / self.temp, dim=-1).cpu()        # the goals only, as on the device
                    mass = torch.softmax(logits, dim=-1)[:, self.gid].sum(dim=-1).cpu()  # sanity: ~1 for a trained model
                    for j, i in enumerate(chunk):
                        out[i] = ({g: float(p[j, n]) for n, g in enumerate(self.goals)}, float(mass[j]))
        return out
