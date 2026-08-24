"""
Detector benchmark command (Phase 6 / task #15). SPEED ONLY — no accuracy claims.

Runs the detector benchmark harness against the deterministic TEST provider (or the
project-created ONNX TEST artifact) over synthetic frames and prints a JSON timing
report. No third-party weights, no dataset, no training.

    python manage.py benchmark_detector [--frames N] [--width W] [--height H]
                                        [--profile quality|balanced|performance]
                                        [--backend test|onnx]
"""
from __future__ import annotations

import json
import os
import tempfile

from django.core.management.base import BaseCommand

from apps.processing.runtime.detector.benchmark import run_benchmark
from apps.processing.runtime.detector.device import DevicePolicy, resolve_device
from apps.processing.runtime.detector.profiles import get_profile
from apps.processing.runtime.detector.test_provider import DeterministicTestProvider


class Command(BaseCommand):
    help = "Benchmark the detector runtime (speed only; no accuracy/mAP)."

    def add_arguments(self, parser):
        parser.add_argument("--frames", type=int, default=60)
        parser.add_argument("--width", type=int, default=1280)
        parser.add_argument("--height", type=int, default=720)
        parser.add_argument("--profile", default="balanced")
        parser.add_argument("--backend", choices=["test", "onnx"], default="test")

    def handle(self, *args, **opts):
        profile = get_profile(opts["profile"])
        if opts["backend"] == "onnx":
            provider = self._onnx_provider(profile)
        else:
            provider = DeterministicTestProvider()
            provider.load(resolve_device(DevicePolicy.CPU_ONLY, "cpu"))

        report = run_benchmark(
            provider, frames=opts["frames"], width=opts["width"], height=opts["height"]
        )
        out = {
            "profile": {
                "key": profile.key, "input_size": profile.input_size,
                "conf": profile.conf, "iou": profile.iou,
                "device_policy": profile.device_policy, "note": profile.note,
            },
            "report": report.to_dict(),
        }
        self.stdout.write(json.dumps(out, indent=2))
        provider.unload()

    def _onnx_provider(self, profile):
        # Build the project-created TEST ONNX artifact and benchmark the ONNX boundary.
        from apps.processing.runtime.detector.onnx_backend import OnnxDetector
        from apps.processing.runtime.detector.testkit import TEST_CLASS_MAP, write_test_onnx

        tmp = tempfile.mkdtemp(prefix="detbench_")
        path = write_test_onnx(os.path.join(tmp, "test.onnx"), target=profile.input_size)
        provider = OnnxDetector(
            onnx_path=path, class_map=TEST_CLASS_MAP,
            provider_name="onnx-test", provider_version="testkit",
            input_size=profile.input_size, conf_threshold=profile.conf,
            iou_threshold=profile.iou, max_detections=300,
        )
        provider.load(resolve_device(DevicePolicy.parse(profile.device_policy), "cpu"))
        provider.warmup()
        return provider
