#!/usr/bin/env python3
"""用 mlx-whisper 在本機聽寫影片，輸出逐字稿 JSON 和一張給校稿用的逐字表。

用法：<WHISPER_PY> transcribe.py <影片> [--lang zh|en|auto] [--hint "店名、人名…"] [--out 逐字稿.json]

逐字表裡可信度低於 0.5 的字會標 ⚠️(0.xx)，校稿時優先處理這些。
"""
import argparse
import json
from pathlib import Path

import mlx_whisper

MODEL = "mlx-community/whisper-large-v3-turbo"  # 第一次用會自動下載約 1.5GB
LOW = 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--lang", default="zh", help="zh＝中文（含中英夾雜）、en＝英文、auto＝自動偵測")
    ap.add_argument("--hint", default="", help="影片會提到的專有名詞，幫辨識對準拼法")
    ap.add_argument("--out", help="逐字稿 JSON 路徑，預設放在影片旁邊")
    a = ap.parse_args()

    prompt = "以下是繁體中文的影片口述。" if a.lang == "zh" else ""
    if a.hint:
        prompt += f"會提到：{a.hint}。"

    r = mlx_whisper.transcribe(
        a.video,
        path_or_hf_repo=MODEL,
        language=None if a.lang == "auto" else a.lang,
        initial_prompt=prompt or None,
        word_timestamps=True,
    )

    out = Path(a.out) if a.out else Path(a.video).with_suffix(".逐字稿.json")
    segs = [
        {
            "start": round(s["start"], 2),
            "end": round(s["end"], 2),
            "text": s["text"].strip(),
            "words": [
                {"w": w["word"].strip(), "start": round(w["start"], 2), "end": round(w["end"], 2), "p": round(w["probability"], 2)}
                for w in s.get("words", [])
            ],
        }
        for s in r["segments"]
    ]
    out.write_text(json.dumps({"language": r.get("language"), "segments": segs}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"語言：{r.get('language')}　逐字稿：{out}\n")
    for s in segs:
        marked = " ".join(
            f"{w['w']}[{w['start']:.1f}]" + (f"⚠️({w['p']:.2f})" if w["p"] < LOW else "") for w in s["words"]
        )
        print(f"{s['start']:6.2f}–{s['end']:6.2f}  {s['text']}\n        {marked}\n")


if __name__ == "__main__":
    main()
