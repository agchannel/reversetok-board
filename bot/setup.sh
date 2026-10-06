#!/bin/bash
# 리버스톡 그로스 텔레그램 봇 설치 (Mac Studio)
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
echo "== 리버스톡 그로스 봇 설치 =="
if [ ! -f .env ]; then
  read -r -p "텔레그램 봇 토큰(BotFather가 준 값): " TOKEN
  read -r -p "현황판 비밀번호: " PW
  CLAUDE_BIN="$(command -v claude || true)"
  if [ -z "$CLAUDE_BIN" ]; then echo "claude 명령을 찾지 못했습니다. Claude Code 설치 후 다시 실행하세요."; exit 1; fi
  printf 'TELEGRAM_TOKEN=%s\nBOARD_PASSWORD=%s\nCLAUDE_BIN=%s\n' "$TOKEN" "$PW" "$CLAUDE_BIN" > .env
  chmod 600 .env
fi
source .env
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q requests cryptography
NODE_DIR="$(dirname "$(command -v node || echo /opt/homebrew/bin/node)")"
PLIST="$HOME/Library/LaunchAgents/com.reversetok.growthbot.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.reversetok.growthbot</string>
<key>ProgramArguments</key><array><string>$DIR/.venv/bin/python</string><string>$DIR/bot.py</string></array>
<key>WorkingDirectory</key><string>$DIR</string>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>$(dirname "$CLAUDE_BIN"):$NODE_DIR:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string><key>HOME</key><string>$HOME</string></dict>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$DIR/bot.log</string><key>StandardErrorPath</key><string>$DIR/bot.log</string>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
sleep 3
echo "== 설치 완료 =="
tail -3 bot.log 2>/dev/null || true
echo "텔레그램에서 봇에게 '/start 비밀번호' 를 보내세요."
