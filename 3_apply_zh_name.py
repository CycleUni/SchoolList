#!/usr/bin/env python3
"""
從 tw_universities.json.progress.json 讀取中文翻譯，
寫入 tw_universities.json 中對應項目的 zh_name 欄位。
若 progress 已有翻譯，則不會覆寫已存在的 zh_name。

參數:
    --input       主檔路徑 (預設 tw_universities.json)
    --progress    進度檔路徑 (預設 <input>.progress.json)
    --overwrite   強制覆寫已有的 zh_name
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="tw_universities.json")
    parser.add_argument("--progress", default=None)
    parser.add_argument("--overwrite", action="store_true", help="強制覆寫已有的 zh_name")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    input_path = (script_dir / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input)
    progress_path = (
        Path(args.progress).resolve()
        if args.progress
        else input_path.with_suffix(input_path.suffix + ".progress.json")
    )

    with input_path.open("r", encoding="utf-8") as f:
        items: list[dict] = json.load(f)
    with progress_path.open("r", encoding="utf-8") as f:
        progress: dict[str, str] = json.load(f)

    progress_by_name: dict[str, str] = {}
    for key, value in progress.items():
        if "|" in key:
            _, name = key.split("|", 1)
            progress_by_name[name] = value

    matched = 0
    skipped: list[str] = []
    unmatched: list[str] = []
    for item in items:
        name = item.get("name")
        if not name:
            continue
        if name not in progress_by_name:
            unmatched.append(name)
            continue
        if not args.overwrite and item.get("zh_name"):
            skipped.append(name)
            continue
        item["zh_name"] = progress_by_name[name]
        matched += 1

    tmp = input_path.with_suffix(input_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    tmp.replace(input_path)

    print(f"已處理 {len(items)} 筆")
    print(f"  寫入 zh_name: {matched} 筆")
    if skipped:
        print(f"  略過 (已有 zh_name): {len(skipped)} 筆")
    if unmatched:
        print(f"  未在 progress 找到: {len(unmatched)} 筆")
        for n in unmatched:
            print(f"    - {n}")
    print(f"已更新: {input_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
