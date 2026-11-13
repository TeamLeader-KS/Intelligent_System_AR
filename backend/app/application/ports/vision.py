from typing import Protocol
from app.application.dtos.analysis import NormalizedImage


class VisionModel(Protocol):
    def analyze(self, image: NormalizedImage, context: dict) -> dict: ...
    def status(self) -> dict: ...
