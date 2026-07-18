"""Immutable frame metadata used by recognition loops."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

import cv2
import numpy as np


@dataclass(frozen=True)
class FrameSnapshot:
    image: np.ndarray
    rect: dict
    fingerprint: str
    standard_deviation: float

    @classmethod
    def from_image(cls, image: np.ndarray, rect: dict) -> "FrameSnapshot":
        if image is None or image.size == 0:
            raise ValueError("Cannot create a snapshot from an empty frame")
        thumbnail = cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)
        fingerprint = hashlib.blake2b(thumbnail.tobytes(), digest_size=12).hexdigest()
        return cls(
            image=image,
            rect=rect.copy(),
            fingerprint=fingerprint,
            standard_deviation=float(image.std()),
        )

    @property
    def is_blank(self) -> bool:
        return self.standard_deviation < 3.0

    def mean_delta(self, previous: "FrameSnapshot | None") -> float:
        if previous is None or previous.image.shape != self.image.shape:
            return 255.0
        if previous.fingerprint == self.fingerprint:
            return 0.0
        return float(cv2.absdiff(self.image, previous.image).mean())
