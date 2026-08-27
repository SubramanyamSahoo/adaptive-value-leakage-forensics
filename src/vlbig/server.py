from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import httpx

from .hf import token
from .registry import ModelSpec


class VLLMServer:
    def __init__(
        self,
        spec: ModelSpec,
        port: int,
        log_dir: str | Path,
        max_model_len: int | None = None,
    ):
        self.spec = spec
        self.port = int(port)
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / f"{spec.key}.server.log"
        self.util_log_path = self.log_dir / f"{spec.key}.gpu.csv"
        self.max_model_len = max_model_len
        self.proc = None
        self.monitor_proc = None
        self._fh = None
        self._util_fh = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def command(self) -> list[str]:
        cmd = [
            "vllm", "serve", self.spec.model_id,
            "--host", "127.0.0.1",
            "--port", str(self.port),
            "--tensor-parallel-size", "1",
            "--dtype", "bfloat16",
        ]
        if self.max_model_len is not None:
            if self.max_model_len < 1:
                raise ValueError("max_model_len must be positive.")
            cmd += ["--max-model-len", str(self.max_model_len)]
        cmd.extend(self.spec.server_args)
        return cmd

    def _start_monitor(self) -> None:
        self._util_fh = self.util_log_path.open("w")
        self.monitor_proc = subprocess.Popen(
            [
                "nvidia-smi",
                "--query-gpu=timestamp,utilization.gpu,memory.used,memory.total,power.draw",
                "--format=csv,noheader,nounits",
                "-l", "1",
            ],
            stdout=self._util_fh,
            stderr=subprocess.DEVNULL,
        )

    def start(self, timeout_s: int) -> None:
        if self.proc is not None:
            raise RuntimeError("Server already running.")
        env = os.environ.copy()
        env["HF_TOKEN"] = token()
        env["CUDA_VISIBLE_DEVICES"] = env.get("CUDA_VISIBLE_DEVICES", "0")
        env["TOKENIZERS_PARALLELISM"] = "true"
        self._fh = self.log_path.open("w")
        cmd = self.command()
        print("SERVER:", " ".join(cmd))
        self.proc = subprocess.Popen(
            cmd, env=env, stdout=self._fh, stderr=subprocess.STDOUT, start_new_session=True
        )
        self._start_monitor()

        deadline = None if timeout_s <= 0 else time.time() + timeout_s
        while deadline is None or time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(
                    f"vLLM exited with {self.proc.returncode}; inspect {self.log_path}"
                )
            try:
                r = httpx.get(f"{self.base_url}/v1/models", timeout=5.0)
                if r.status_code == 200:
                    print("READY:", self.spec.model_id)
                    return
            except Exception:
                pass
            time.sleep(3)
        raise TimeoutError(f"Timed out waiting for vLLM; inspect {self.log_path}")

    def stop(self) -> None:
        if self.proc is not None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.proc = None

        if self.monitor_proc is not None:
            self.monitor_proc.terminate()
            try:
                self.monitor_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.monitor_proc.kill()
            self.monitor_proc = None

        if self._fh:
            self._fh.close()
            self._fh = None
        if self._util_fh:
            self._util_fh.close()
            self._util_fh = None
