from datetime import datetime
import json

from app.paths import LOGS_DIR

def log_event(event: dict) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    log_path = LOGS_DIR / "transcription_log.jsonl"
    event["timestamp"] = datetime.now().isoformat(timespec="seconds")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

