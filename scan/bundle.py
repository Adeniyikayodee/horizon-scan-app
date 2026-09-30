"""The scan's own material, carried in a secret rather than in the repository.

A scan profile is the institute's thinking: its question, its criteria, the themes it
works in, the organizations it watches, and the framing the agents read. That belongs
to the institute, so it does not sit in a public repository. Instead it travels as one
base64 zip in the host's secrets, and the app unpacks it on startup into the same paths
the code already expects, so nothing else changes.

Pack it from a working copy that has the files:

    python -m scan.bundle pack            # writes bundle.b64 and a line to paste

Then set that value as PROFILE_BUNDLE_B64 in the host's secrets. Locally the files are
already on disk, so nothing is unpacked and nothing is overwritten.
"""
from __future__ import annotations

import base64
import io
import sys
import zipfile
from pathlib import Path

from . import config

SECRET = "PROFILE_BUNDLE_B64"

# What a scan needs to run, and what a public repository should not hold.
PACKED = ("context", "profiles")
# Never pack a run's own output, a pilot, or an evaluation note: those are findings,
# not configuration, and they are the most sensitive part of a client's work.
SKIP = ("/run/", "/demo/", "/pilot", "/eval/", "__pycache__", ".DS_Store")


def _wanted(rel: str) -> bool:
    r = "/" + rel.replace("\\", "/")
    return not any(s in r for s in SKIP)


def pack(root: Path | None = None) -> str:
    """Base64 of a zip holding the scan's material, from a working copy that has it."""
    root = root or config.ROOT
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for top in PACKED:
            base = root / top
            if not base.exists():
                continue
            for p in sorted(base.rglob("*")):
                if p.is_file() and _wanted(str(p.relative_to(root))):
                    z.write(p, str(p.relative_to(root)))
    return base64.b64encode(buf.getvalue()).decode("ascii")


def contents(b64: str) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(b64))) as z:
        return z.namelist()


def install(b64: str, root: Path | None = None, overwrite: bool = False) -> list[str]:
    """Unpack the bundle, skipping any file already on disk unless told otherwise, so a
    working copy is never overwritten by whatever the host happens to hold."""
    root = root or config.ROOT
    written = []
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(b64))) as z:
        for name in z.namelist():
            if not _wanted(name) or name.endswith("/"):
                continue
            target = (root / name).resolve()
            if not str(target).startswith(str(Path(root).resolve())):
                continue                       # a zip must never write outside the root
            if target.exists() and not overwrite:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(name))
            written.append(name)
    return written


def profile_installed(name: str, root: Path | None = None) -> bool:
    return ((root or config.ROOT) / "profiles" / name / "profile.json").exists()


def ensure(b64: str, root: Path | None = None) -> list[str]:
    """Install the bundle when there is one and the material is not already here."""
    if not b64 or not b64.strip():
        return []
    try:
        return install(b64.strip(), root)
    except Exception:
        return []


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "pack":
        data = pack()
        out = config.ROOT / "bundle.b64"
        out.write_text(data, encoding="utf-8")
        files = contents(data)
        print(f"wrote {out} : {len(files)} files, {len(data):,} characters of base64")
        print(f"first files: {', '.join(files[:4])} ...")
        print(f"\nPaste this into the host's secrets, on one line:\n{SECRET} = \"<the contents of "
              f"{out.name}>\"")
    else:
        print("usage: python -m scan.bundle pack")
