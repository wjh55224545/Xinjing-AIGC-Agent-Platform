#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""vibraimage_engine 一键构建脚本。

用法:
    python scripts/release/build_wheel.py

产物: vibraimage_engine/dist/vibraimage_engine-<version>-py3-none-any.whl
依赖: pip install build wheel
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO_ROOT / "vibraimage_engine"


def main() -> int:
    if not (ENGINE_DIR / "pyproject.toml").exists():
        print(f"[错误] 未找到 {ENGINE_DIR / 'pyproject.toml'}，请确认在仓库根目录运行")
        return 1

    print("==> 构建 vibraimage_engine wheel ...")
    proc = subprocess.run(
        [sys.executable, "-m", "build", "--wheel"],
        cwd=str(ENGINE_DIR),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        print("[错误] 构建失败，请先执行: pip install build wheel")
        return proc.returncode

    wheels = sorted((ENGINE_DIR / "dist").glob("*.whl"))
    if not wheels:
        print("[错误] 构建完成但未找到 wheel 产物")
        return 1
    whl = wheels[-1]
    print(f"==> 构建成功: {whl.name} ({whl.stat().st_size / 1024:.1f} KB)")
    print("==> 下一步：将 wheel 作为资产上传到 GitHub Release，或通过 PyPI 发布")
    return 0


if __name__ == "__main__":
    sys.exit(main())
