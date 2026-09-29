#!/bin/bash
# 檢查上字幕需要的工具是否齊全。只檢查、不安裝；缺什麼會印出安裝指令，由 Claude 徵得使用者同意後再跑。
# 最後一行印出 WHISPER_PY=<路徑>，給 transcribe.py 用。

ok=1
say() { printf '%s\n' "$*"; }

# 1. Apple 晶片（mlx-whisper 只支援 Apple 晶片）
if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  say "❌ 這台不是 Apple 晶片的 Mac（M1 以後）。語音辨識用的 mlx-whisper 跑不了。"
  exit 2
fi
say "✅ Apple 晶片 Mac"

# 剛裝好 Homebrew、還沒設定路徑時，brew 會找不到；先把 Homebrew 的路徑載入再檢查
if ! command -v brew >/dev/null 2>&1 && [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
  say "⚠️ Homebrew 已安裝，但路徑還沒設定。請 Claude 把 eval \"\$(/opt/homebrew/bin/brew shellenv)\" 加進 ~/.zprofile。"
fi

# 2. ffmpeg：要能燒字幕（ass 濾鏡）；zscale 用來把 iPhone HDR 轉一般色彩，缺了只是 HDR 影片顏色可能偏灰
if command -v ffmpeg >/dev/null 2>&1; then
  filters=$(ffmpeg -hide_banner -filters 2>/dev/null)
  if echo "$filters" | grep -qE '^ .{3} ass '; then
    say "✅ ffmpeg（$(command -v ffmpeg)）可以燒字幕"
  else
    say "❌ ffmpeg 缺字幕功能（libass）。請改裝完整版：brew install ffmpeg"
    ok=0
  fi
  if echo "$filters" | grep -qE '^ .{3} zscale '; then
    say "✅ ffmpeg 支援 HDR 轉換"
  else
    say "⚠️ ffmpeg 不支援 HDR 轉換（zscale）。一般影片不受影響；iPhone HDR 影片燒出來顏色可能偏灰。"
  fi
  if [ "$(file -b "$(command -v ffmpeg)" | grep -c x86_64)" = "1" ] && ! file -b "$(command -v ffmpeg)" | grep -q arm64; then
    say "⚠️ 這個 ffmpeg 是 Intel 版，靠 Rosetta 轉譯在跑，燒錄會比較慢，但能用。"
  fi
else
  say "❌ 沒有 ffmpeg"
  if command -v brew >/dev/null 2>&1; then
    say "   安裝：brew install ffmpeg"
  else
    say "   先裝 Homebrew（Mac 的免費安裝工具，要輸入一次電腦密碼）："
    say '   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    say "   裝好後再跑：brew install ffmpeg"
  fi
  ok=0
fi

# 3. mlx-whisper：找它自己用的 Python
WHISPER_PY=""
if command -v mlx_whisper >/dev/null 2>&1; then
  shebang=$(head -1 "$(command -v mlx_whisper)" | sed 's/^#!//')
  if [ -x "$shebang" ] && "$shebang" -c "import mlx_whisper" 2>/dev/null; then WHISPER_PY="$shebang"; fi
fi
if [ -z "$WHISPER_PY" ] && python3 -c "import mlx_whisper" 2>/dev/null; then WHISPER_PY=$(command -v python3); fi

if [ -n "$WHISPER_PY" ]; then
  say "✅ mlx-whisper（語音辨識）"
else
  say "❌ 沒有 mlx-whisper（語音辨識）"
  if command -v uv >/dev/null 2>&1; then
    say "   安裝：uv tool install mlx-whisper"
  else
    say "   先裝 uv（Python 安裝工具，不用密碼）：curl -LsSf https://astral.sh/uv/install.sh | sh"
    say "   再裝：~/.local/bin/uv tool install mlx-whisper"
  fi
  ok=0
fi

[ $ok = 1 ] && say "全部就緒。" || say "還有東西要裝，裝完再跑一次這支檢查。"
echo "WHISPER_PY=$WHISPER_PY"
[ $ok = 1 ]
