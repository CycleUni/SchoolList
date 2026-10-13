#!/usr/bin/env python3
"""
合併 <地區>_universities.json 與 schools.json 既有項目，產生符合 bulk-import
格式的 schools.json。

規則:
  - 以 email_domain 為鍵（與後端 School.email_domain 的唯一鍵一致），既有項目保留
  - 輸入檔中尚未存在的 email_domain 依序新增
  - email_domain 取 domains[0]
  - translations 原樣帶過（台灣是 zh-TW、香港是 zh-HK），不寫死語言代碼
  - 每一筆都帶 region，對應 CycleUni 的 Region.code
  - 每一筆都帶 code（學校短碼，例如 NTU），同一地區內不重複；已有 code 的項目保留原值
  - city 依 CITY_BY_DOMAIN 重新填入；表上沒有的學校不帶 city

為什麼 region 是必填：後端 AdminSchoolBulkImportView 會把 item['region'] 直接
寫進 School.region_id，而該欄位不可為空。少了它，整批匯入會在建立第一筆新學校
時就失敗；帶錯了則會讓某地區的學生用另一地區的校園信箱通過驗證。

參數:
    --input       輸入 JSON 路徑 (預設 tw_universities.json)
    --region      這批資料所屬地區代碼 (預設 TW)
    --source      schools.json 路徑 (預設 schools.json)
    --output      輸出檔路徑 (預設 schools.json)
    --cities-only 不合併輸入檔，只依 CITY_BY_DOMAIN 重新填 city
"""

import argparse
import json
import re
import sys
from pathlib import Path

# 學校短碼（School.code）的規則與後端 accounts/school_codes.py 相同：取
# email_domain 第一段轉大寫，只留英數與「-」，最多 20 字元；同一地區內撞號
# 依序加 -2、-3。短碼只需在地區內唯一——台灣的弘光科大與香港大學都可以是 HKU。
#
# 規則算不出常用簡稱時在這裡指定，以 email_domain 為鍵：
#   s.eduhk.hk      第一段是 "s"（學生信箱子網域）
#   ust.hk          慣用 HKUST，與後端種子資料一致
#   sce.pccu.edu.tw 第一段是推廣教育部的 "sce"
#   ln.edu.hk       嶺南大學的官方簡稱是 LingU
CODE_OVERRIDES = {
    "s.eduhk.hk": "EDUHK",
    "ust.hk": "HKUST",
    "sce.pccu.edu.tw": "PCCU",
    "ln.edu.hk": "LINGU",
}
CODE_MAX_LENGTH = 20

# 學校所屬城市：CycleUni City.code（後端 core/default_cities.py）。
# 臺灣是 22 縣市的 ISO 3166-2:TW 代碼，以主校區所在地為準；香港分 HKI 港島、
# KLN 九龍、NT 新界。所選學校沒有書時，首頁與搜尋會改顯示同城市的書。
# 不在表上的學校不輸出 city 欄位，匯入時保留後台設定的城市，而不是清掉它。
CITY_BY_DOMAIN = {
    # 臺北市
    "ntu.edu.tw": "TPE", "ntnu.edu.tw": "TPE", "ntust.edu.tw": "TPE", "nccu.edu.tw": "TPE",
    "ntut.edu.tw": "TPE", "scu.edu.tw": "TPE", "sce.pccu.edu.tw": "TPE", "shu.edu.tw": "TPE",
    "mcu.edu.tw": "TPE", "nchulc.edu.tw": "TPE", "nia.edu.tw": "TPE", "ntcn.edu.tw": "TPE",
    "ntptc.edu.tw": "TPE", "scc.edu.tw": "TPE", "tmc.edu.tw": "TPE", "tmtc.edu.tw": "TPE",
    "tpec.edu.tw": "TPE", "ttu.edu.tw": "TPE", "ntue.edu.tw": "TPE", "utaipei.edu.tw": "TPE",
    # 新北市
    "fju.edu.tw": "NWT", "tku.edu.tw": "NWT", "au.edu.tw": "NWT", "hfu.edu.tw": "NWT",
    "nou.edu.tw": "NWT", "ntca.edu.tw": "NWT", "ntpu.edu.tw": "NWT", "sjsmit.edu.tw": "NWT",
    "chihlee.edu.tw": "NWT",
    # 基隆市
    "cku.edu.tw": "KEE", "ntou.edu.tw": "KEE",
    # 桃園市
    "ncu.edu.tw": "TAO", "cgu.edu.tw": "TAO", "cpu.edu.tw": "TAO", "cycu.edu.tw": "TAO",
    "lhu.edu.tw": "TAO", "ncpes.edu.tw": "TAO", "yzu.edu.tw": "TAO",
    # 新竹市
    "nthu.edu.tw": "HSZ", "nycu.edu.tw": "HSZ", "chu.edu.tw": "HSZ", "hcu.edu.tw": "HSZ",
    "nhctc.edu.tw": "HSZ",
    # 苗栗縣
    "nuu.edu.tw": "MIA",
    # 臺中市
    "nchu.edu.tw": "TXG", "thu.edu.tw": "TXG", "cmc.edu.tw": "TXG", "csmc.edu.tw": "TXG",
    "cyut.edu.tw": "TXG", "fcu.edu.tw": "TXG", "ltc.edu.tw": "TXG", "ntcpe.edu.tw": "TXG",
    "ntctc.edu.tw": "TXG", "pu.edu.tw": "TXG", "ltu.edu.tw": "TXG", "ncut.edu.tw": "TXG",
    "asia.edu.tw": "TXG",
    # 彰化縣
    "dyu.edu.tw": "CHA", "ncue.edu.tw": "CHA",
    # 南投縣
    "ncnu.edu.tw": "NAN",
    # 雲林縣
    "nfu.edu.tw": "YUN", "yuntech.edu.tw": "YUN",
    # 嘉義市
    "ncyu.edu.tw": "CYI", "ttit.edu.tw": "CYI",
    # 嘉義縣
    "ccu.edu.tw": "CYQ", "nhu.edu.tw": "CYQ",
    # 臺南市
    "ncku.edu.tw": "TNN", "chna.edu.tw": "TNN", "cju.edu.tw": "TNN", "ksu.edu.tw": "TNN",
    "ntntc.edu.tw": "TNN", "stut.edu.tw": "TNN", "tnca.edu.tw": "TNN",
    # 高雄市
    "nsysu.edu.tw": "KHH", "isu.edu.tw": "KHH", "kmc.edu.tw": "KHH", "nkust.edu.tw": "KHH",
    "nknu.edu.tw": "KHH", "nuk.edu.tw": "KHH", "ouk.edu.tw": "KHH",
    # 屏東縣
    "npttc.edu.tw": "PIF", "npust.edu.tw": "PIF",
    # 宜蘭縣
    "niu.edu.tw": "ILA",
    # 花蓮縣
    "ndhu.edu.tw": "HUA", "nhltc.edu.tw": "HUA", "tcu.edu.tw": "HUA",
    # 臺東縣
    "ntttc.edu.tw": "TTT",
    # 香港：港島
    "hku.hk": "HKI", "hkapa.edu": "HKI", "hksyu.edu": "HKI",
    # 香港：九龍
    "cityu.edu.hk": "KLN", "hkbu.edu.hk": "KLN", "hkmu.edu.hk": "KLN", "polyu.edu.hk": "KLN",
    # 香港：新界
    "chuhai.edu.hk": "NT", "cuhk.edu.hk": "NT", "ln.edu.hk": "NT", "ust.hk": "NT",
    "s.eduhk.hk": "NT", "hsu.edu.hk": "NT",
}


def normalize_code(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def derive_code(email_domain: str) -> str:
    first = (email_domain or "").strip().split(".")[0]
    return re.sub(r"[^A-Z0-9-]", "", first.upper())[:CODE_MAX_LENGTH] or "SCHOOL"


def dedupe_code(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    n = 2
    while True:
        suffix = f"-{n}"
        candidate = base[:CODE_MAX_LENGTH - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
        n += 1


def assign_codes(items: list[dict]) -> list[str]:
    """補上缺少的 code，回傳補上的清單。已指定的 code 先佔位，推導出的才不會搶走。"""
    taken: dict[str, set[str]] = {}
    for it in items:
        if it.get("code"):
            it["code"] = normalize_code(it["code"])
            taken.setdefault(it.get("region"), set()).add(it["code"])
    assigned: list[str] = []
    for it in items:
        if it.get("code"):
            continue
        domain = it.get("email_domain", "")
        region_taken = taken.setdefault(it.get("region"), set())
        base = CODE_OVERRIDES.get(domain) or derive_code(domain)
        it["code"] = dedupe_code(base, region_taken)
        region_taken.add(it["code"])
        assigned.append(f'{it["code"]} ({domain})')
    return assigned


def resolve(script_dir: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (script_dir / value).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="tw_universities.json")
    parser.add_argument("--region", default="TW")
    parser.add_argument("--source", default="schools.json")
    parser.add_argument("--output", default="schools.json")
    parser.add_argument("--cities-only", action="store_true")
    args = parser.parse_args()

    region = args.region.upper()
    script_dir = Path(__file__).resolve().parent
    input_path = resolve(script_dir, args.input)
    source_path = resolve(script_dir, args.source)
    output_path = resolve(script_dir, args.output)

    with input_path.open("r", encoding="utf-8") as f:
        incoming: list[dict] = json.load(f)
    if args.cities_only:
        incoming = []

    existing_items: list[dict] = []
    if source_path.exists():
        with source_path.open("r", encoding="utf-8") as f:
            source = json.load(f)
        if isinstance(source, dict) and "items" in source:
            existing_items = source["items"]
        elif isinstance(source, list):
            existing_items = source

    # Keyed on email_domain rather than name: that is what the import endpoint
    # matches on, and two institutions can legitimately share a display name
    # across regions (see The Chinese University of Hong Kong).
    existing_domains = {it["email_domain"] for it in existing_items if "email_domain" in it}

    merged: list[dict] = list(existing_items)
    added: list[str] = []
    skipped: list[str] = []

    for it in incoming:
        name = it.get("name")
        if not name:
            continue
        domains = it.get("domains") or []
        if not domains:
            print(f"警告: {name} 沒有 domains，略過", file=sys.stderr)
            continue
        domain = domains[0]
        if domain in existing_domains:
            skipped.append(name)
            continue

        translations = it.get("translations") or {}
        if not translations:
            print(f"警告: {name} 沒有任何翻譯，略過", file=sys.stderr)
            continue

        entry = {
            "name": name,
            "email_domain": domain,
            "region": region,
            "translations": translations,
        }
        if it.get("code"):
            entry["code"] = it["code"]
        merged.append(entry)
        added.append(name)
        existing_domains.add(domain)

    # 來源資料同一所學校可能以不同英文拼法出現兩次（例如 National Tsing Hua
    # University 與 National Tsinghua University 共用 nthu.edu.tw）。
    # email_domain 在後端是唯一鍵，重複項會讓每次匯入都把校名在兩個拼法之間
    # 改來改去並回報成 modified，所以在輸出前收斂成第一筆。
    deduped: list[dict] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    for it in merged:
        domain = it.get("email_domain")
        if domain in seen:
            duplicates.append(f'{it.get("name")} ({domain})')
            continue
        seen.add(domain)
        deduped.append(it)
    if duplicates:
        print(f"email_domain 重複，已收斂 {len(duplicates)} 筆:", file=sys.stderr)
        for d in duplicates:
            print(f"  {d}", file=sys.stderr)
    merged = deduped

    assigned = assign_codes(merged)

    # 每次重跑都以 CITY_BY_DOMAIN 為準，表上改了城市就會反映到輸出。
    no_city: list[str] = []
    for it in merged:
        city = CITY_BY_DOMAIN.get(it.get("email_domain"))
        if city:
            it["city"] = city
        else:
            it.pop("city", None)
            no_city.append(it.get("email_domain"))

    output = {"items": merged}
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    tmp.replace(output_path)

    # 輸出分區檔案
    region_items = {}
    for it in merged:
        r = it.get("region")
        if r:
            region_items.setdefault(r, []).append(it)
            
    for r, items in region_items.items():
        r_path = output_path.with_name(f"schools.{r}.json")
        r_output = {"items": items}
        r_tmp = r_path.with_suffix(r_path.suffix + ".tmp")
        with r_tmp.open("w", encoding="utf-8") as f:
            json.dump(r_output, f, ensure_ascii=False, indent=2)
        r_tmp.replace(r_path)

    by_region: dict[str, int] = {}
    for it in merged:
        by_region[it.get("region", "(未設定)")] = by_region.get(it.get("region", "(未設定)"), 0) + 1

    print(f"既有項目: {len(existing_items)} 筆")
    if no_city:
        print(f"沒有城市 {len(no_city)} 筆: {', '.join(no_city)}", file=sys.stderr)
    print(f"從 {input_path.name} 新增 ({region}): {len(added)} 筆")
    if skipped:
        print(f"email_domain 已存在略過: {len(skipped)} 筆")
    print(f"輸出總計: {len(merged)} 筆 -> {output_path}")
    for r, items in region_items.items():
        print(f"  分區輸出: {len(items)} 筆 -> schools.{r}.json")
    print("  各地區:", ", ".join(f"{k}={v}" for k, v in sorted(by_region.items())))
    if assigned:
        print(f"補上短碼: {len(assigned)} 筆")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
