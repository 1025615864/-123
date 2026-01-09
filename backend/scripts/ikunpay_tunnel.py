import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)


def _resolve_env_file_path(env_file: str) -> Path:
    p = Path(env_file)
    if p.is_absolute():
        return p
    backend_root = Path(__file__).resolve().parents[1]
    return backend_root / env_file


def _update_env_file(env_path: Path, notify_url: str) -> None:
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    out: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith("IKUNPAY_NOTIFY_URL="):
            out.append(f"IKUNPAY_NOTIFY_URL={notify_url}")
            replaced = True
        else:
            out.append(line)

    if not replaced:
        out.append(f"IKUNPAY_NOTIFY_URL={notify_url}")

    env_path.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")


def _find_cloudflared() -> str | None:
    p = (os.getenv("CLOUDFLARED_PATH") or "").strip()
    if p and Path(p).exists():
        return p

    found = shutil.which("cloudflared") or shutil.which("cloudflared.exe")
    if found:
        return found

    userprofile = (os.getenv("USERPROFILE") or "").strip()
    if userprofile:
        candidates = [
            Path(userprofile)
            / "AppData"
            / "Local"
            / "Microsoft"
            / "WinGet"
            / "Packages"
            / "Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe"
            / "cloudflared.exe",
        ]
        for cand in candidates:
            if cand.exists():
                return str(cand)

    return None


def main() -> int:
    cloudflared = _find_cloudflared()
    if not cloudflared:
        sys.stderr.write("cloudflared not found. Set CLOUDFLARED_PATH or install it.\n")
        return 2

    backend_url = (os.getenv("TUNNEL_URL") or "http://127.0.0.1:8000").strip()

    env_file = (os.getenv("ENV_FILE") or "env.local").strip()
    env_path = _resolve_env_file_path(env_file)

    proc = subprocess.Popen(
        [cloudflared, "tunnel", "--url", backend_url],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    found_public_url: str | None = None
    start = time.time()

    try:
        assert proc.stdout is not None
        while True:
            line = proc.stdout.readline()
            if line:
                sys.stdout.write(line)
                sys.stdout.flush()

                m = _URL_RE.search(line)
                if m and not found_public_url:
                    found_public_url = m.group(0)
                    notify_url = f"{found_public_url}/api/payment/ikunpay/notify"
                    _update_env_file(env_path, notify_url)
                    sys.stdout.write(f"IKUNPAY_NOTIFY_URL updated: {notify_url}\n")
                    sys.stdout.flush()

            if proc.poll() is not None:
                return int(proc.returncode or 0)

            if not found_public_url and (time.time() - start) > 30:
                sys.stderr.write("Timed out waiting for trycloudflare URL\n")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
                return 3

    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
