#!/usr/bin/env python3
"""把 SRT 字幕燒進影片。每條字幕第一行是主語言（大字），第二行起是翻譯（小字），沒有第二行就是單語。

用法：python3 burn_subs.py <影片> <字幕.srt> <輸出.mp4> [--short-side 1080] [--margin-v 0.245]

- 直式影片預設輸出 1080×1920（IG／Shorts 規格），橫式輸出 1920×1080；--short-side 0 維持原解析度。
- iPhone 的 HDR（HLG／PQ）影片會自動轉成一般色彩，避免上社群顏色發灰或過亮。
- 樣式：白字黑描邊、不加底。直式預設落在畫面約 75% 高度，避開 IG／Shorts 底部的按鈕與文案區。
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

FONT = "PingFang TC"  # macOS 內建繁中字體
BASE = dict(main_size=54, sub_size=38, outline=4, shadow=2, margin_lr=60)  # 以短邊 1080 為基準


def probe(video):
    info = subprocess.run(["ffmpeg", "-hide_banner", "-i", video], capture_output=True, text=True).stderr
    hdr = bool(re.search(r"arib-std-b67|smpte2084", info))
    m = re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", info)
    if not m:
        sys.exit(f"讀不到影片畫面資訊：{video}")
    w, h = int(m.group(1)), int(m.group(2))
    rot = re.search(r"rotation of (-?[\d.]+)", info)
    if rot and abs(float(rot.group(1))) % 180 == 90:
        w, h = h, w  # 手機直拍的影片常存成橫的再標旋轉，ffmpeg 會自動轉正
    return w, h, hdr


def has_filter(name):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return re.search(rf"^ .{{3}} {name} ", out, re.M) is not None


def has_encoder(name):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    return f" {name} " in out


def ts(t):  # SRT 時間碼 → ASS 時間碼
    h, m, s, ms = map(int, re.split(r"[:,.]", t.strip()))
    return f"{h}:{m:02d}:{s:02d}.{ms // 10:02d}"


def srt_to_ass(srt_text, w, h, margin_v_ratio):
    k = min(w, h) / 1080
    s = {n: round(v * k) for n, v in BASE.items()}
    margin_v = round(h * margin_v_ratio)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT},{s['main_size']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{s['outline']},{s['shadow']},2,{s['margin_lr']},{s['margin_lr']},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for block in re.split(r"\n\s*\n", srt_text.strip()):
        rows = [r for r in block.strip().splitlines() if r.strip()]
        if len(rows) < 3 or "-->" not in rows[1]:
            continue
        start, end = rows[1].split("-->")
        main = rows[2].strip()
        sub = " ".join(r.strip() for r in rows[3:])
        text = main + (f"\\N{{\\fs{s['sub_size']}\\b0}}{sub}" if sub else "")
        events.append(f"Dialogue: 0,{ts(start)},{ts(end)},Default,,0,0,0,,{text}")
    if not events:
        sys.exit("SRT 裡沒有讀到任何字幕，檢查格式（序號、時間碼、文字，每條之間空一行）。")
    return head + "\n".join(events) + "\n", len(events)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("srt")
    ap.add_argument("out")
    ap.add_argument("--short-side", type=int, default=1080, help="輸出短邊像素；0＝維持原解析度")
    ap.add_argument("--margin-v", type=float, help="字幕底部離畫面底的比例；直式預設 0.245、橫式 0.08")
    a = ap.parse_args()

    w, h, hdr = probe(a.video)
    k = (a.short_side / min(w, h)) if a.short_side else 1
    out_w, out_h = round(w * k / 2) * 2, round(h * k / 2) * 2
    margin_v = a.margin_v if a.margin_v is not None else (0.245 if h > w else 0.08)

    ass, n = srt_to_ass(Path(a.srt).read_text(encoding="utf-8-sig"), out_w, out_h, margin_v)
    ass_path = Path(tempfile.mkdtemp()) / "subs.ass"
    ass_path.write_text(ass, encoding="utf-8")

    vf = []
    if hdr and has_filter("zscale"):
        vf.append("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
                  "tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv")
    elif hdr:
        print("⚠️ 這支是 HDR 影片，但 ffmpeg 沒有 zscale，略過色彩轉換，成品顏色可能偏灰。", file=sys.stderr)
    vf += [f"scale={out_w}:{out_h}:flags=lanczos", "format=yuv420p", f"ass={ass_path}"]

    if has_encoder("libx264"):
        venc = ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-maxrate", "8M", "-bufsize", "16M"]
    else:
        venc = ["-c:v", "h264_videotoolbox", "-b:v", "8M"]

    cmd = ["ffmpeg", "-v", "error", "-y", "-i", a.video, "-map", "0:v:0", "-map", "0:a:0?",
           "-vf", ",".join(vf), *venc,
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out]
    print(f"{w}x{h}{' HDR' if hdr else ''} → {out_w}x{out_h}，{n} 條字幕，燒錄中…", file=sys.stderr)
    subprocess.run(cmd, check=True)
    print(a.out)


if __name__ == "__main__":
    main()
