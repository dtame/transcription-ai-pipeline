import re
from pathlib import Path


TIMESTAMP_PATTERN = re.compile(
    r"^\[(?P<start>\d{2}:\d{2}(?::\d{2})?)\s*->\s*(?P<end>\d{2}:\d{2}(?::\d{2})?)\]\s*(?P<text>.*)$"
)


def timestamp_to_seconds(timestamp: str) -> int:
    parts = [int(part) for part in timestamp.split(":")]

    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds

    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


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
                    "start_seconds": None,
                    "end_seconds": None,
                    "text": line,
                    "line_number": line_number,
                    "valid": False
                })
                continue

            start = match.group("start")
            end = match.group("end")

            segments.append({
                "start": start,
                "end": end,
                "start_seconds": timestamp_to_seconds(start),
                "end_seconds": timestamp_to_seconds(end),
                "text": match.group("text").strip(),
                "line_number": line_number,
                "valid": True
            })

    return segments