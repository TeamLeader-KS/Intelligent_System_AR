"""Download the pinned single-class corrosion checkpoint as an unevaluated candidate."""
import argparse
import hashlib
from pathlib import Path
from urllib.request import urlopen

BASE = "https://raw.githubusercontent.com/aziz-hizem/spiderbot-rust-detection/d077206d805333b689637766287a6f80ec470946/"
FILES = {
    "v1_yolov8n.pt": ("models/v1_yolov8n.pt", "23616c79be9487c96a4230c11285414b9377544320775c68843afee9b15f2cd4"),
    "LICENSE": ("LICENSE", "75d85fad373e62b866a89b74cf9f1614c596324eb7503e41584177d43ed90ffd"),
    "UPSTREAM.md": ("README.md", "1ca6b58d67de0675da1a5555157d45c298f6012a237c1bbbb0523200d798e1f4"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("ai/candidates/spiderbot"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, (remote, digest) in FILES.items():
        destination = args.output / name
        if destination.exists():
            content = destination.read_bytes()
        else:
            with urlopen(BASE + remote, timeout=30) as response:
                content = response.read(16 * 1024 * 1024 + 1)
        if len(content) > 16 * 1024 * 1024 or hashlib.sha256(content).hexdigest() != digest:
            parser.error(f"Checksum mismatch: {name}. Existing files are not overwritten.")
        temporary = args.output / (name + ".download")
        temporary.write_bytes(content)
        temporary.replace(destination)
    print("Downloaded checked candidate, not deployed. Class 0 is Corrosion; APK uses a different contract.")


if __name__ == "__main__":
    main()
