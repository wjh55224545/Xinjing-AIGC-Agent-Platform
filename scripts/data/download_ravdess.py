# -*- coding: utf-8 -*-
"""
RAVDESS 选择性下载脚本
======================

文献: Livingstone SR, Russo FA (2018) The Ryerson Audio-Visual Database of
      Emotional Speech and Song (RAVDESS): A dynamic, multimodal set of facial
      and vocal expressions in North American English.
      PLoS ONE 13(5): e0196391. https://doi.org/10.1371/journal.pone.0196391

许可: CC BY-NC-SA 4.0（非商业、署名、相同方式共享）。
      视频/音频数据文件不随本仓库分发，仅通过本脚本按需下载，用于
      科研/教学场景的算法验证。下载后请在成果中按上述文献引用。

用法示例（Windows）:
    python scripts/data/download_ravdess.py --actors 01 02 --modalities video
    python scripts/data/download_ravdess.py --actors 01 --modalities audio,video

默认只下载前 2 位演员的视频包（约 1GB），避免全量 24.8GB。
"""

import argparse
import hashlib
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

ZENODO_RECORD = "1188976"
ZENODO_BASE = f"https://zenodo.org/record/{ZENODO_RECORD}/files"

# 各文件 md5（取自 Zenodo 页面）
FILE_MD5 = {
    "Audio_Song_Actors_01-24.zip": "5411230427d67a21e18aa4d466e6d1b9",
    "Audio_Speech_Actors_01-24.zip": "bc696df654c87fed845eb13823edef8a",
    "Video_Speech_Actor_01.zip": None,
    "Video_Speech_Actor_02.zip": None,
    "Video_Speech_Actor_03.zip": None,
    "Video_Speech_Actor_04.zip": None,
}

# 已知的语音视频包 md5（按需补充；None 时跳过校验）
VIDEO_SPEECH_MD5 = {
    "01": None,
    "02": None,
}


def build_url(filename: str) -> str:
    return f"{ZENODO_BASE}/{filename}?download=1"


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(url: str, dest: Path, expected_md5: str | None = None) -> None:
    if dest.exists() and expected_md5 and md5_of(dest) == expected_md5:
        print(f"[skip] 已存在且校验通过: {dest.name}")
        return
    print(f"[下载] {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    if expected_md5:
        actual = md5_of(tmp)
        if actual != expected_md5:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"md5 校验失败: {dest.name} 期望 {expected_md5} 实际 {actual}")
    os.replace(tmp, dest)
    print(f"[完成] {dest.name} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")


def unzip_if_needed(zip_path: Path, out_dir: Path) -> None:
    marker = out_dir / (zip_path.stem + ".ok")
    if marker.exists():
        print(f"[skip] 已解压: {zip_path.name}")
        return
    print(f"[解压] {zip_path.name} -> {out_dir}")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(out_dir)
    marker.touch()
    print(f"[完成] 解压 {zip_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="RAVDESS 选择性下载")
    parser.add_argument("--actors", nargs="+", default=["01", "02"],
                        help="要下载的演员编号，如 01 02（默认 01 02）")
    parser.add_argument("--modalities", nargs="+", default=["video"],
                        choices=["audio", "video"],
                        help="要下载的模态（默认 video）")
    parser.add_argument("--data-dir", type=Path, default=Path("data/ravdess"),
                        help="数据存放目录（默认 data/ravdess，已 gitignore）")
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    zips_dir = data_dir / "zips"
    raw_dir = data_dir / "raw"
    zips_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    tasks: list[str] = []
    if "audio" in args.modalities:
        tasks.extend(["Audio_Speech_Actors_01-24.zip"])
    if "video" in args.modalities:
        tasks.extend([f"Video_Speech_Actor_{a}.zip" for a in args.actors])

    total_bytes = 0
    for name in tasks:
        dest = zips_dir / name
        download_file(build_url(name), dest, FILE_MD5.get(name))
        total_bytes += dest.stat().st_size
        if name.startswith("Video_Speech_"):
            unzip_if_needed(dest, raw_dir)

    print(f"\n下载完成: {len(tasks)} 个包, 共 {total_bytes / 1024 / 1024:.1f} MB")
    print(f"数据目录: {data_dir}")
    print("提醒: RAVDESS 采用 CC BY-NC-SA 4.0 许可，仅限非商业用途，请引用文献 "
          "Livingstone & Russo (2018), PLoS ONE 13(5): e0196391.")


if __name__ == "__main__":
    sys.exit(main())
