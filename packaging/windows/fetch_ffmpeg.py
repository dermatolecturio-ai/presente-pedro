"""Baixa ffmpeg essentials (Windows) para packaging/windows/ffmpeg/bin."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from urllib.request import urlopen

URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
ROOT = Path(__file__).resolve().parent
DEST = ROOT / "ffmpeg" / "bin"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    if (DEST / "ffmpeg.exe").is_file():
        print("ffmpeg.exe ja existe")
        return 0

    print(f"Baixando {URL} ...")
    with urlopen(URL, timeout=180) as resp:  # noqa: S310
        data = resp.read()

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = [n for n in zf.namelist() if "/bin/" in n.replace("\\", "/")]
        for name in members:
            base = Path(name.replace("\\", "/")).name
            if not base:
                continue
            target = DEST / base
            with zf.open(name) as src, open(target, "wb") as out:
                out.write(src.read())

    if not (DEST / "ffmpeg.exe").is_file():
        raise SystemExit("ffmpeg.exe nao encontrado apos extrair")
    print(f"OK -> {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
