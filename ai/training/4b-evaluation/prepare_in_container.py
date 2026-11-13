"""Isolated 4B preparation. Does not modify production 2B pin or environment.
Run: docker compose run --rm --no-deps --user 1000:1000 -T vision-prepare python - < ai/training/4b-evaluation/prepare_in_container.py
Uses existing audited HTTPS redirect, SHA256 and atomic cache helpers.
"""
import fcntl, hashlib, json, re
from pathlib import Path
import httpx
from vision_prepare import fetch, download_blob, verified, PreparationError
MODEL = "qwen3-vl:4b-instruct"
PIN = "84f7ed8042fa7cdbd902f7dcb7d0370e032095047cc3244179f263b77b5bc318"
RAW = b'{"schemaVersion":2,"mediaType":"application/vnd.docker.distribution.manifest.v2+json","config":{"mediaType":"application/vnd.docker.container.image.v1+json","digest":"sha256:a67151e7009487ea73bb4377d878c1e3d89f19c8ae05422d76e86935e3273fa6","size":206},"layers":[{"mediaType":"application/vnd.ollama.image.model","digest":"sha256:3a859c4dca6883593e389a08987f04762f2a374d475cabc1538360473a72b1da","size":2497888288,"from":"dhiltgen/qwen3-vl:4b-instruct-q4_K_M-llamacpp"},{"mediaType":"application/vnd.ollama.image.projector","digest":"sha256:70ac570fd36b65a64fbb99883c34d5196368c1cf8f63d8402802a34a0ed2b363","size":839325760,"from":"dhiltgen/qwen3-vl:4b-instruct-q4_K_M-llamacpp"},{"mediaType":"application/vnd.ollama.image.license","digest":"sha256:7339fa418c9ad3e8e12e74ad0fd26a9cc4be8703f9c110728a992b193be85cb2","size":11355,"from":"dhiltgen/qwen3-vl:4b-instruct-q4_K_M-llamacpp"},{"mediaType":"application/vnd.ollama.image.params","digest":"sha256:f6417cb1e26962991f8e875a93f3cb0f92bc9b4955e004881251ccbf934a19d2","size":42,"from":"dhiltgen/qwen3-vl:4b-instruct-q4_K_M-llamacpp"}],"runner":"llamacpp","format":"gguf"}'
assert hashlib.sha256(RAW).hexdigest() == PIN
manifest = json.loads(RAW)
blobs = [manifest["config"], *manifest["layers"]]
assert manifest["schemaVersion"] == 2 and len(blobs) == 5
assert sum(b["size"] for b in blobs) <= 3_500_000_000
assert all(type(b["size"]) is int and 0 < b["size"] <= 3_500_000_000 and re.fullmatch(r"sha256:[0-9a-f]{64}",b["digest"]) for b in blobs)
root = Path("/models/models")
two_b = root / "manifests/registry.ollama.ai/library/qwen3-vl/2b-instruct"
previous_2b = hashlib.sha256(two_b.read_bytes()).hexdigest() if two_b.exists() else None
with Path("/models/.vision-prepare.lock").open("r") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with httpx.Client(timeout=httpx.Timeout(240, connect=30), verify=True, follow_redirects=False) as client:
        chunks = bytearray()
        def consume(parts):
            for part in parts:
                chunks.extend(part)
                if len(chunks) > 65536:
                    raise PreparationError("Manifest exceeds limit")
        fetch(client, "https://registry.ollama.ai/v2/library/qwen3-vl/manifests/4b-instruct", consume)
        assert bytes(chunks) == RAW, "Official manifest changed; explicit review required"
        for blob in blobs:
            download_blob(client, root, blob)
            assert verified(root / "blobs" / blob["digest"].replace(":", "-", 1),blob)
    target = root / "manifests/registry.ollama.ai/library/qwen3-vl/4b-instruct"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert target.read_bytes() == RAW, "Existing 4B tag differs; not overwriting"
    else:
        staged = target.with_suffix(".4b-experiment-partial")
        staged.write_bytes(RAW)
        staged.replace(target)
    assert (hashlib.sha256(two_b.read_bytes()).hexdigest() if two_b.exists() else None) == previous_2b
    print(json.dumps({"status":"VERIFIED_NEW_TAG_READY","model":MODEL,"manifest_sha256":PIN,"total_bytes":sum(b["size"] for b in blobs),"production_2b_sha256_unchanged":previous_2b}),flush=True)
