#!/usr/bin/env python3
"""
使用 OpenAI 相容端點 (NVIDIA integrate) 為 tw_universities.json 內每所大學加上繁體中文 (zh-TW) 翻譯。
支援續跑：完成翻譯的項目會寫入 progress 檔，中斷後下次執行會自動略過已完成的項目。

環境變數 (會自動載入同目錄或工作目錄下的 .env 檔):
    OPENAI_API_KEY         API key (必填)

參數:
    --model       模型名稱 (預設 openai/gpt-oss-120b)
    --limit       最多翻譯幾筆 (方便測試; 不指定則翻譯全部)
    --input       輸入 JSON 路徑 (預設 tw_universities.json)
    --progress    進度檔路徑 (預設 <input>.progress.json)

安裝依賴: pip install -r requirements.txt
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


MAX_RETRIES = 6
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
INITIAL_BACKOFF = 2.0
MAX_BACKOFF = 60.0


PROMPT_TEMPLATE = (
    "You are a translator specialized in Taiwan higher education. "
    "Translate the following English university name into its standard Traditional Chinese (zh-TW) name as used in Taiwan.\n\n"
    "Rules:\n"
    "1. Output must be Traditional Chinese (zh-TW) used in Taiwan's official context.\n"
    "2. If it is a Taiwanese university, use its official Chinese name (including prefixes like 國立 / 私立).\n"
    "3. If it is a foreign university's branch campus or language school in Taiwan, use the conventional translation.\n"
    "4. If you cannot determine a name or there is no conventional translation, output: null.\n\n"
    "Response format (strict):\n"
    "- Do ALL reasoning internally.\n"
    "- Your final visible message MUST contain ONLY the translated name string (or the single word null).\n"
    "- Do not include quotes, punctuation, explanations, or any extra text in the final message.\n\n"
    "English university name: {name}\n\n"
    "Final answer:"
)

OPENAI_BASE_URL = "https://integrate.api.nvidia.com/v1"


def call_openai(name: str, model: str, client: OpenAI, timeout: int = 30, reasoning_effort: str = "low") -> str | None:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": PROMPT_TEMPLATE.format(name=name)},
        ],
        temperature=0.2,
        max_tokens=2048,
        timeout=timeout,
        extra_body={"reasoning_effort": reasoning_effort},
    )
    if not response.choices:
        return None
    msg = response.choices[0].message
    text = (getattr(msg, "content", None) or "").strip()
    if not text or text.lower() in {"null", "none", "n/a"}:
        reasoning = (getattr(msg, "reasoning_content", None) or "").strip()
        recovered = extract_final_answer(reasoning) if reasoning else ""
        if recovered:
            print(f"\n  [debug] content empty, recovered from reasoning: {recovered!r}", end="")
            text = recovered
        else:
            print(f"\n  [debug] content={text!r} reasoning={(reasoning or '')[:200]!r}", end="")
            return None
    return text


def extract_final_answer(reasoning: str) -> str:
    import re
    if not reasoning:
        return ""
    if re.search(r"\boutput[:\s]+null\b", reasoning, flags=re.IGNORECASE):
        if not re.search(r"[一-鿿]", reasoning.split("output null")[-1]):
            return ""
    quoted = re.findall(r"[「『`\"]([^「」『`\"\n]{2,40})[」』`\"]", reasoning)
    zh_quoted = [q.strip() for q in quoted if re.search(r"[一-鿿]", q)]
    if zh_quoted:
        return zh_quoted[-1]
    lines = [ln.strip() for ln in reasoning.strip().splitlines() if ln.strip()]
    for ln in reversed(lines):
        if re.fullmatch(r"[一-鿿\s]{2,40}", ln):
            return ln
    return ""


def normalize(value: str) -> str:
    return value.strip().strip('"').strip("「」").strip()


def load_progress(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {}


def save_progress(path: Path, progress: dict[str, str]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="tw_universities.json")
    parser.add_argument("--progress", default=None, help="進度檔路徑 (預設 <input>.progress.json)")
    parser.add_argument("--model", default="openai/gpt-oss-120b")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=5, help="每筆 API 呼叫間隔秒數 (避免觸發 rate limit)")
    parser.add_argument("--reasoning-effort", default="medium", choices=["low", "medium", "high"], help="推理強度 (gpt-oss 推薦 medium)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("錯誤: 請先設定環境變數 OPENAI_API_KEY", file=sys.stderr)
        return 1

    client = OpenAI(api_key=api_key, base_url=OPENAI_BASE_URL)

    script_dir = Path(__file__).resolve().parent
    input_path = (script_dir / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input)
    progress_path = (
        Path(args.progress).resolve()
        if args.progress
        else input_path.with_suffix(input_path.suffix + ".progress.json")
    )

    with input_path.open("r", encoding="utf-8") as f:
        items: list[dict] = json.load(f)

    progress = load_progress(progress_path)
    print(f"已從進度檔載入 {len(progress)} 筆既有翻譯 ({progress_path})")

    todo: list[tuple[int, dict]] = []
    for idx, item in enumerate(items):
        name = item.get("name")
        if not name:
            continue
        key = f"{idx}|{name}"
        if key in progress:
            item["translations"] = {"zh-TW": {"name": progress[key]}}
            continue
        todo.append((idx, item))

    if args.limit is not None:
        todo = todo[: args.limit]
    print(f"待翻譯: {len(todo)} 筆 (總筆數 {len(items)})")

    failed: list[str] = []
    for i, (idx, item) in enumerate(todo, 1):
        name = item["name"]
        key = f"{idx}|{name}"
        print(f"[{i}/{len(todo)}] {name} ... ", end="", flush=True)
        try:
            translated = call_openai(name, args.model, client, reasoning_effort=args.reasoning_effort)
        except Exception as e:
            print(f"錯誤: {type(e).__name__}: {e}")
            failed.append(name)
            time.sleep(2)
            continue

        if not translated:
            print("無法取得翻譯 (回傳空值)")
            failed.append(name)
            continue

        translated = normalize(translated)
        progress[key] = translated
        item["translations"] = {"zh-TW": {"name": translated}}
        save_progress(progress_path, progress)
        print(translated)

        if args.sleep > 0:
            time.sleep(args.sleep)

    with input_path.open("w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    save_progress(progress_path, progress)

    print(f"\n完成。共處理 {len(todo)} 筆，失敗 {len(failed)} 筆。")
    if failed:
        print("失敗清單:")
        for n in failed:
            print(f"  - {n}")
    print(f"進度檔: {progress_path}")
    print(f"已更新: {input_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
