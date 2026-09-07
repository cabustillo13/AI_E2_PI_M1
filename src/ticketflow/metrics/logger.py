import json
from datetime import datetime, timezone
from pathlib import Path


class MetricsLogger:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def log(self, **data) -> None:
        record = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            **data,
        }

        with self.path.open(
            "a",
            encoding="utf-8",
        ) as file:

            file.write(
                json.dumps(record) + "\n"
            )