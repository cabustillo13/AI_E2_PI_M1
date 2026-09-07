import json
from datetime import datetime
from pathlib import Path


def log_metric(ticket: str, category: str, metrics: dict):
    """Guarda las métricas operativas en formato JSONL."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "ticket_preview": ticket[:60] + "...",
        "category": category,
        **metrics
    }
    
    # Asegura que el directorio exista
    Path("data").mkdir(exist_ok=True)
    
    with open("data/metrics.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")