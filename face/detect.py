"""Face detection and encoding.

Primary path: `face_recognition` (dlib HOG/CNN detector + 128-d embedding).
Fallback path: OpenCV's Haar cascade, used only if `face_recognition` /
dlib isn't installed (it requires a C++ toolchain + CMake and is a common
install snag on Windows). The fallback gives a crop but no embedding.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PIL import Image


class NoFaceDetectedError(Exception):
    """Raised when no face could be found in the input image."""


@dataclass
class FaceResult:
    face_image_path: str
    bbox: Tuple[int, int, int, int]  # (top, right, bottom, left)
    encoding: Optional[List[float]]
    method: str  # "face_recognition" or "opencv_haar"


def _detect_with_face_recognition(image_path: str, output_dir: str) -> FaceResult:
    import face_recognition  # imported lazily so the haar fallback works without it

    image = face_recognition.load_image_file(image_path)
    locations = face_recognition.face_locations(image)
    if not locations:
        raise NoFaceDetectedError(f"No face found in {image_path}")

    top, right, bottom, left = locations[0]
    encodings = face_recognition.face_encodings(image, known_face_locations=[locations[0]])
    encoding = encodings[0].tolist() if encodings else None

    crop = image[top:bottom, left:right]
    out_path = os.path.join(output_dir, "face_crop.png")
    Image.fromarray(crop).save(out_path)

    return FaceResult(
        face_image_path=out_path,
        bbox=(top, right, bottom, left),
        encoding=encoding,
        method="face_recognition",
    )


def _detect_with_opencv_haar(image_path: str, output_dir: str) -> FaceResult:
    import cv2

    img = cv2.imread(image_path)
    if img is None:
        raise NoFaceDetectedError(f"Could not read image {image_path}")

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))

    if len(faces) == 0:
        raise NoFaceDetectedError(f"No face found in {image_path}")

    x, y, w, h = faces[0]
    crop = img[y : y + h, x : x + w]
    out_path = os.path.join(output_dir, "face_crop.png")
    cv2.imwrite(out_path, crop)

    return FaceResult(
        face_image_path=out_path,
        bbox=(y, x + w, y + h, x),
        encoding=None,
        method="opencv_haar",
    )


def detect_face(image_path: str, output_dir: str) -> FaceResult:
    """Detect the primary face in `image_path` and save a cropped copy into
    `output_dir`. Tries face_recognition first, falls back to OpenCV Haar
    cascades if dlib/face_recognition isn't available."""
    os.makedirs(output_dir, exist_ok=True)

    try:
        import face_recognition  # noqa: F401
    except ImportError:
        return _detect_with_opencv_haar(image_path, output_dir)

    return _detect_with_face_recognition(image_path, output_dir)
