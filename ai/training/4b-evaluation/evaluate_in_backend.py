"""Three real 4B development probes using the unchanged production adapter/prompt.
Run after preparation: docker compose exec -T backend python - < ai/training/4b-evaluation/evaluate_in_backend.py > ai/training/4b-evaluation/results.jsonl
No DB writes. No model/environment/production file changes. Do not run alongside another inference.
"""
import hashlib, inspect, json, os, time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import httpx
from PIL import Image
from app.application.dtos.analysis import NormalizedImage
from app.infrastructure.local_vision import OllamaVision
from app.domain.server_vision import validate_vision_result
from app.domain.errors import AnalysisError
MODEL = "qwen3-vl:4b-instruct"
PIN = "84f7ed8042fa7cdbd902f7dcb7d0370e032095047cc3244179f263b77b5bc318"
CASES = [{'id': 'normal_ksb', 'source_file': 'ai/demo/pumps/ksb-etanorm.jpg', 'sha256': 'f142906db310a07f71e956e6fe036e0eef05bad13dfab623357177e17ed72ac4'}, {'id': 'exposed_coupling_synthetic', 'source_file': 'ai/demo/pumps/guard-missing-demo.webp', 'sha256': '481805c1dc8c9bade8fc0e86fec58ab5d6c798034e50271d167b26315271a0c5', 'original_png_sha256_before_parallel_asset_conversion': '033df3ce8826390019ec020b4341fd5d9dd49976c8321399059e312f20eeb55f'}, {'id': 'oil_below_min_synthetic', 'source_file': 'ai/demo/pumps/oil-low-demo.webp', 'sha256': 'd66b1cc8b1e81ce4d881990f793b77d695f95a8708658831713c66491a3af2f4', 'original_png_sha256_before_parallel_asset_conversion': '86c6fb09b67378e543b7f45ffe680ff642c0e25330f926430c8d7e200bb369df'}]
CONTEXT = {"components": []}
original_post = httpx.Client.post
trace = {}
def trace_post(client, url, **kwargs):
    if str(url).endswith("/api/chat"):
        payload = kwargs["json"]
        trace["prompt_sha256"] = hashlib.sha256(payload["messages"][0]["content"].encode()).hexdigest()
        trace["schema_sha256"] = hashlib.sha256(json.dumps(payload["format"], sort_keys=True).encode()).hexdigest()
        trace["options"] = payload["options"]
        trace["request_image_sha256"] = hashlib.sha256(payload["messages"][0]["images"][0].encode()).hexdigest()
        response = original_post(client, url, **kwargs)
        try:
            trace["raw_ollama_response"] = response.json()
        except ValueError:
            trace["response_status"] = response.status_code
            trace["non_json_response"] = True
        return response
    return original_post(client, url, **kwargs)
adapter = OllamaVision(os.environ["VISION_BASE_URL"], MODEL, timeout=240)
state = adapter.status()
assert state["state"] == "READY" and state["digest"] == PIN, state
assert len(CASES) == 3
httpx.Client.post = trace_post
for index, case in enumerate(CASES):
    trace.clear()
    path = Path("/app/cv-demo/pumps") / Path(case["source_file"]).name
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == case["sha256"], case["id"]
    with Image.open(BytesIO(raw)) as image:
        normalized = NormalizedImage(raw,image.width,image.height,Image.MIME.get(image.format,"image/jpeg"))
    record = {"case":case["id"],"source_file":case["source_file"],"source_sha256":case["sha256"],
              "model_status":state,"production_config_model_unchanged":os.environ["VISION_MODEL"],
              "adapter_sha256":hashlib.sha256(inspect.getsource(OllamaVision).encode()).hexdigest(),
              "started_at":datetime.now(timezone.utc).isoformat(),"sequence_index":index,"context":CONTEXT,
              "classification":"FAMILIAR_DEVELOPMENT_PROBE_NOT_ACCURACY_METRIC","timeout_seconds":240}
    start = time.perf_counter()
    try:
        reply = adapter.analyze(normalized, CONTEXT)
        record.update(reply=reply,validated=validate_vision_result(reply["result"],[]),error=None)
    except AnalysisError as error:
        record["error"] = {"code":error.code,"message":str(error)}
    record.update(trace)
    record["wall_ms"] = round((time.perf_counter()-start)*1000)
    print(json.dumps(record,ensure_ascii=False),flush=True)
httpx.Client.post = original_post
