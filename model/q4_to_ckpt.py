#!/usr/bin/env python3
"""q4_to_ckpt.py - turn a device model (export_q4.py's 4-bit "ak42" v3 file) back into a train.py-style
checkpoint, so probe_fish.py can measure a model that only exists as model_q4.bin (the shipped one, issue #1).

The weights are the 4-bit values times their fp16 group scales: what the device multiplies with.

    python3 q4_to_ckpt.py out/model_q4.bin /tmp/shipped_q4.pt
    python3 probe_fish.py --ckpt /tmp/shipped_q4.pt --seed 11
"""
import argparse, os, struct, sys
import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "llama2.c"))
from model import ModelArgs, Transformer  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("q4")
    ap.add_argument("out")
    a = ap.parse_args()
    b = open(a.q4, "rb").read()
    magic, version = struct.unpack_from("Ii", b, 0)
    if magic != 0x616B3432 or version != 3:
        sys.exit(f"{a.q4}: not an export_q4.py file (magic {magic:#x}, version {version})")
    dim, hidden, n_layers, n_heads, n_kv, vocab, seq = struct.unpack_from("7i", b, 8)
    shared = struct.unpack_from("B", b, 36)[0]
    gs = struct.unpack_from("i", b, 37)[0]
    off = 256

    def fp32(n):
        nonlocal off
        t = torch.from_numpy(np.frombuffer(b, np.float32, n, off).copy()); off += 4 * n
        return t

    def q4(shape):
        nonlocal off
        n = int(np.prod(shape))
        u = np.frombuffer(b, np.uint8, n // 2, off); off += n // 2
        s = np.frombuffer(b, np.float16, n // gs, off).astype(np.float32); off += 2 * (n // gs)
        q = np.empty(n, np.int8); q[0::2] = (u & 15).astype(np.int8) - 8; q[1::2] = (u >> 4).astype(np.int8) - 8
        return torch.from_numpy((q.reshape(-1, gs).astype(np.float32) * s[:, None]).reshape(shape))

    kv = dim // n_heads * n_kv
    att = [fp32(dim) for _ in range(n_layers)]
    ffn = [fp32(dim) for _ in range(n_layers)]
    norm = fp32(dim)
    sd = {"tok_embeddings.weight": q4((vocab, dim))}
    for name, shape in (("attention.wq", (dim, dim)), ("attention.wk", (kv, dim)), ("attention.wv", (kv, dim)),
                        ("attention.wo", (dim, dim)), ("feed_forward.w1", (hidden, dim)),
                        ("feed_forward.w2", (dim, hidden)), ("feed_forward.w3", (hidden, dim))):
        for i in range(n_layers):
            sd[f"layers.{i}.{name}.weight"] = q4(shape)
    sd["output.weight"] = sd["tok_embeddings.weight"] if shared else q4((vocab, dim))
    if off != len(b):
        sys.exit(f"{a.q4}: read {off} of {len(b)} bytes: layout mismatch")
    for i in range(n_layers):
        sd[f"layers.{i}.attention_norm.weight"] = att[i]
        sd[f"layers.{i}.ffn_norm.weight"] = ffn[i]
    sd["norm.weight"] = norm
    args = dict(dim=dim, n_layers=n_layers, n_heads=n_heads, n_kv_heads=n_kv, vocab_size=vocab,
                hidden_dim=hidden, max_seq_len=seq, dropout=0.0)
    m = Transformer(ModelArgs(**args))
    m.load_state_dict(sd, strict=True)   # every tensor accounted for
    torch.save({"model_args": args, "model": m.state_dict(), "source": os.path.basename(a.q4)}, a.out)
    print(f"{a.out}: dim {dim}, hidden {hidden}, layers {n_layers}, heads {n_heads}/{n_kv}, vocab {vocab}, "
          f"seq {seq}, shared {shared}, GS {gs}, {sum(t.numel() for t in m.parameters())/1e6:.2f}M params")


if __name__ == "__main__":
    main()
