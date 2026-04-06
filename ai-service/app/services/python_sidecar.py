from __future__ import annotations

import atexit
import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PythonSidecarClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root_dir = Path(__file__).resolve().parents[3]
        self.python_dir = self.root_dir / "python"
        self._lock = threading.Lock()
        atexit.register(self.close)

    def analyze_video(self, video_path: str, fps: float) -> dict[str, Any]:
        with self._lock:
            env = os.environ.copy()
            env.update(
                {
                    "MODEL_PATH": self.settings.yolo_model_path,
                    "LOCAL_MODEL_PATH": self.settings.rf_model_path,
                    "LABEL_MAPPING_PATH": self.settings.rf_label_mapping_path,
                    "USE_GPU": env.get("USE_GPU", "true"),
                }
            )
            command = [
                os.environ.get("PYTHON_BIN", "python3"),
                "-c",
                (
                    "import json, os, sys; "
                    "sys.path.insert(0, os.getcwd()); "
                    "import yolov8_service; "
                    "result = yolov8_service.analyze_video_file(sys.argv[1], float(sys.argv[2])); "
                    "print(json.dumps(result))"
                ),
                video_path,
                str(fps),
            ]
            logger.info("Running legacy python analysis subprocess for video=%s", Path(video_path).name)
            completed = subprocess.run(
                command,
                cwd=str(self.python_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=240,
            )
            if completed.returncode != 0:
                stderr = completed.stderr.strip()
                stdout = completed.stdout.strip()
                raise RuntimeError(
                    "Legacy python analysis failed: "
                    f"returncode={completed.returncode} stderr={stderr or '<empty>'} stdout={stdout or '<empty>'}"
                )
            lines = [line for line in completed.stdout.splitlines() if line.strip()]
            if not lines:
                raise RuntimeError("Legacy python analysis produced no output")
            return json.loads(lines[-1])

    def close(self) -> None:
        return
