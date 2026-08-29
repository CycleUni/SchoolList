#!/usr/bin/env python3
"""
從 world_universities_and_domains.json 篩選出指定地區的大學，輸出成
<地區小寫>_universities.json。

地區代碼用的是來源資料的 alpha_two_code，剛好與 CycleUni 的 Region.code
（ISO 3166-1 alpha-2）相同，所以篩出來的檔案可以直接對應到一個地區。

排除清單的存在理由：來源資料把一些非學位機構、以及設在其他地區的分校也
標成同一個 alpha_two_code。這些混進來會讓校園信箱驗證放行錯誤的網域，
所以在管線最前面就濾掉，而不是留到後面靠人工檢查。

參數:
    --country     地區代碼 (預設 TW)
    --input       來源 JSON (預設 world_universities_and_domains.json)
    --output      輸出路徑 (預設 <country 小寫>_universities.json)
"""

import argparse
import json
import os

INPUT_FILE = "world_universities_and_domains.json"

# key 是地區代碼，value 是該地區要排除的 domains[0]。
EXCLUDED_DOMAINS = {
    "HK": {
        # K-12 國際學校，不是大學。
        "cdnis.edu.hk",
        # 香港中文大學（深圳）——校名相同但位於中國大陸，網域也是 .cn。
        # 留著會讓一所香港的大學看起來有兩個合法的校園信箱網域。
        "cuhk.edu.cn",
    },
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", default="TW", help="地區代碼，例如 TW 或 HK")
    parser.add_argument("--input", default=INPUT_FILE)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    country = args.country.upper()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, args.input)
    output_name = args.output or f"{country.lower()}_universities.json"
    output_path = os.path.join(script_dir, output_name)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    excluded = EXCLUDED_DOMAINS.get(country, set())
    matched = [item for item in data if item.get("alpha_two_code") == country]

    kept, dropped = [], []
    for item in matched:
        domains = item.get("domains") or []
        if domains and domains[0] in excluded:
            dropped.append(f"{item.get('name')} ({domains[0]})")
            continue
        kept.append(item)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)

    print(f"✅ 篩選完成！{country} 共 {len(matched)} 筆，保留 {len(kept)} 筆。")
    for name in dropped:
        print(f"   排除: {name}")
    print(f"   輸出檔案: {output_path}")


if __name__ == "__main__":
    main()
