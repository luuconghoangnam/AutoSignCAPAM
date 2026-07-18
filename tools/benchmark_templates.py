"""Benchmark current templates against a collected screenshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from vision.template_matcher import find_device_rdp_button


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--device", choices=("12", "200"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    image = cv2.imread(str(args.image))
    if image is None:
        parser.error(f"Cannot read image: {args.image}")
    result = find_device_rdp_button(image, args.device, return_details=True)
    report = {
        "image": str(args.image),
        "device": args.device,
        "result": result,
    }
    text = json.dumps(report, indent=2, ensure_ascii=True)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0 if result else 2


if __name__ == "__main__":
    raise SystemExit(main())
