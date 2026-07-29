#!/usr/bin/env python3
"""
篩選 world_universities_and_domains.json 中 alpha_two_code 為 "TW" 的大學資料，
輸出到 tw_universities.json。
"""

import json
import os

INPUT_FILE = "world_universities_and_domains.json"
OUTPUT_FILE = "tw_universities.json"


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, INPUT_FILE)
    output_path = os.path.join(script_dir, OUTPUT_FILE)

    # Read the full JSON
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Filter for TW
    tw_data = [item for item in data if item.get("alpha_two_code") == "TW"]

    # Write result
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tw_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 篩選完成！共找到 {len(tw_data)} 筆台灣大學資料。")
    print(f"   輸出檔案: {output_path}")


if __name__ == "__main__":
    main()