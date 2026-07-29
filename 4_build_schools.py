#!/usr/bin/env python3
"""
合併 tw_universities.json (含中文翻譯) 與 schools.json 既有項目，
產生符合 bulk-import 格式的 schools.json。

規則:
  - schools.json 既有項目保留原 email_domain
  - tw_universities.json 中尚未在 schools.json 的項目依 name 新增
  - tw_universities.json 的 email_domain 取 domains[0]
  - 中文名取 translations.zh-TW.name

參數:
    --input       tw_universities.json 路徑 (預設 tw_universities.json)
    --source      schools.json 路徑 (預設 schools.json)
    --output      輸出檔路徑 (預設 schools.json)
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="tw_universities.json")
    parser.add_argument("--source", default="schools.json")
    parser.add_argument("--output", default="schools.json")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    input_path = (script_dir / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input)
    source_path = (script_dir / args.source).resolve() if not Path(args.source).is_absolute() else Path(args.source)
    output_path = (script_dir / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)

    with input_path.open("r", encoding="utf-8") as f:
        tw_items: list[dict] = json.load(f)

    existing_items: list[dict] = []
    if source_path.exists():
        with source_path.open("r", encoding="utf-8") as f:
            source = json.load(f)
        if isinstance(source, dict) and "items" in source:
            existing_items = source["items"]
            existing_names = {it["name"] for it in existing_items if "name" in it}
        elif isinstance(source, list):
            existing_items = source
            existing_names = {it["name"] for it in existing_items if "name" in it}
        else:
            existing_names = set()
    else:
        existing_names = set()

    merged: list[dict] = list(existing_items)
    added: list[str] = []
    skipped: list[str] = []

    for it in tw_items:
        name = it.get("name")
        if not name:
            continue
        if name in existing_names:
            skipped.append(name)
            continue
        domains = it.get("domains") or []
        if not domains:
            print(f"警告: {name} 沒有 domains，略過", file=sys.stderr)
            continue
        zh_name = it.get("translations", {}).get("zh-TW", {}).get("name")
        if not zh_name:
            print(f"警告: {name} 沒有中文翻譯，略過", file=sys.stderr)
            continue
        merged.append({
            "name": name,
            "email_domain": domains[0],
            "translations": {"zh-TW": {"name": zh_name}},
        })
        added.append(name)

    output = {"items": merged}
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    tmp.replace(output_path)

    print(f"既有項目: {len(existing_items)} 筆")
    print(f"從 tw 新增: {len(added)} 筆")
    if skipped:
        print(f"已存在略過: {len(skipped)} 筆")
    print(f"輸出總計: {len(merged)} 筆 -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
