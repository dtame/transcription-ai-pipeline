from datetime import datetime
import json

from app.paths import LOGS_DIR


def log_event(event) -> None:
    LOGS_DIR.mkdir(exist_ok=True)

    log_path = LOGS_DIR / "transcription_log.jsonl"

    if isinstance(event, str):
        event = {
            "message": event
        }

    event["timestamp"] = datetime.now().isoformat(
        timespec="seconds"
    )

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                event,
                ensure_ascii=False
            ) + "\n"
        )