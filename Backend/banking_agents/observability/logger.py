import json
import logging
import time
from datetime import datetime, timezone
from collections import deque
from pathlib import Path
from threading import Lock

# Log file goes at Backend/logs/harness.jsonl
# Path resolution: relative to this file's location:
# This file is at Backend/banking_agents/observability/logger.py
# So Backend/ is 3 levels up: Path(__file__).parent.parent.parent
LOG_DIR = Path(__file__).parent.parent.parent / "logs"

class HarnessLogger:
    _instance = None
    _singleton_lock = Lock()

    def __new__(cls):
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._log_path = LOG_DIR / "harness.jsonl"
        self._buffer = deque(maxlen=500)
        self._buffer_lock = Lock()
        self._file_lock = Lock()

    def log(self, event_type: str, **kwargs) -> dict:
        try:
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event": event_type,
                **kwargs,
            }
            with self._buffer_lock:
                self._buffer.append(entry)
            self._write_to_file(entry)
            return entry
        except Exception:
            logging.exception("HarnessLogger.log failed silently")
            return {}

    def _write_to_file(self, entry: dict):
        try:
            with self._file_lock:
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
        except Exception:
            logging.exception("HarnessLogger._write_to_file failed silently")

    def log_agent_call(self, agent: str, tool: str, latency_ms: int,
                       status: str, session_id: str, detail: str = ""):
        return self.log("agent_call", agent=agent, tool=tool,
                        latency_ms=latency_ms, status=status,
                        session_id=session_id, detail=detail)

    def log_model_call(self, model_id: str, latency_ms: int,
                       input_tokens: int = 0, output_tokens: int = 0):
        return self.log("model_call", model=model_id, latency_ms=latency_ms,
                        input_tokens=input_tokens, output_tokens=output_tokens)

    def log_guardrail_event(self, rule_type: str, triggered: bool,
                            detail: str, session_id: str = ""):
        return self.log("guardrail_trigger", rule=rule_type, triggered=triggered,
                        detail=detail, session_id=session_id)

    def log_kill_switch_event(self, agent_name: str, action: str, triggered_by: str):
        return self.log("kill_switch_toggle", agent=agent_name, action=action,
                        triggered_by=triggered_by)

    def log_session(self, event: str, session_id: str, query: str = "", intent: str = ""):
        return self.log(event, session_id=session_id, query=query, intent=intent)

    def get_recent(self, n: int = 100) -> list:
        with self._buffer_lock:
            items = list(self._buffer)
        return list(reversed(items[-n:]))

harness_logger = HarnessLogger()
