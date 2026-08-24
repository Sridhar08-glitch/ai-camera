"""
GPU training benchmark (Phase 6T-B preflight). SPEED/VRAM ONLY — no real data, no
accuracy. Measures training-step throughput + peak VRAM for the real architecture
candidate(s) at practical batch sizes on the local GPU, using random TEST_ONLY
tensors. Used to estimate 6T-B training duration. Trains no real detector.
"""
from __future__ import annotations

import time

import torch


def _fcos(num_classes=6, input_size=640):
    # Use the finalized training adapter's model config (min=max=input_size,
    # mean0/std1) so the benchmark reflects the real training path.
    from training.detector_adapter import FcosTrainingAdapter
    return FcosTrainingAdapter().build_model(num_classes, input_size)


def _rand_targets(batch, size, device, n_boxes=3, num_classes=6):
    targets = []
    g = torch.Generator(device="cpu").manual_seed(0)
    for _ in range(batch):
        xy = torch.rand(n_boxes, 2, generator=g) * (size * 0.5)
        wh = torch.rand(n_boxes, 2, generator=g) * (size * 0.3) + 5
        boxes = torch.cat([xy, xy + wh], dim=1).to(device)
        labels = torch.randint(0, num_classes, (n_boxes,), generator=g).to(device)
        targets.append({"boxes": boxes, "labels": labels})
    return targets


def bench_fcos(batch, size=640, steps=6, amp=True, num_classes=6) -> dict:
    device = "cuda"
    torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
    model = _fcos(num_classes, size).to(device).train()
    opt = torch.optim.SGD(model.parameters(), lr=0.01, momentum=0.9)
    scaler = torch.amp.GradScaler("cuda", enabled=amp)
    imgs = [torch.rand(3, size, size, device=device) for _ in range(batch)]
    targets = _rand_targets(batch, size, device, num_classes=num_classes)

    # warmup
    for _ in range(2):
        opt.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", enabled=amp):
            loss = sum(model(imgs, targets).values())
        scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(steps):
        opt.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", enabled=amp):
            loss = sum(model(imgs, targets).values())
        scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
    torch.cuda.synchronize()
    dt = time.perf_counter() - t0

    peak = torch.cuda.max_memory_allocated() / 1e6
    imgs_per_s = (batch * steps) / dt
    del model, opt, imgs, targets; torch.cuda.empty_cache()
    return {"batch": batch, "size": size, "amp": amp, "steps": steps,
            "sec": round(dt, 3), "steps_per_s": round(steps / dt, 3),
            "imgs_per_s": round(imgs_per_s, 2), "peak_vram_mb": round(peak, 1)}


def run(batches=(2, 4, 8), size=640):
    import json
    if not torch.cuda.is_available():
        print(json.dumps({"error": "CUDA not available"})); return
    print(f"# device={torch.cuda.get_device_name(0)} size={size} amp=True")
    for b in batches:
        try:
            print(json.dumps(bench_fcos(b, size=size)))
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                torch.cuda.empty_cache()
                print(json.dumps({"batch": b, "size": size, "oom": True}))
            else:
                raise


if __name__ == "__main__":
    run()
