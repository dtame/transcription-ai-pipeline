# book/transcript_parser.py

import re
from pathlib import Path


TIMESTAMP_PATTERN = re.compile(
    r"^\[(?P<start>\d{2}:\d{2}(?::\d{2})?)\s*->\s*(?P<end>\d{2}:\d{2}(?::\d{2})?)\]\s*(?P<text>.*)$"
)


def parse_transcript_file(file_path: Path) -> list[dict]:
    segments = []

    with open(file_path, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            match = TIMESTAMP_PATTERN.match(line)

            if not match:
                segments.append({
                    "start": None,
                    "end": None,
                    "text": line,
                    "line_number": line_number,
                    "valid": False
                })
                continue

            segments.append({
                "start": match.group("start"),
                "end": match.group("end"),
                "text": match.group("text").strip(),
                "line_number": line_number,
                "valid": True
            })

    return segments