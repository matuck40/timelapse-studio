#!/bin/zsh
# Sobe o painel em segundo plano. O servidor sobrevive ao fechar a janela.

set -u

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

SCRIPT_DIR="${0:A:h}"
PROJECT_DIR="${SCRIPT_DIR:h}"
PID_FILE="$PROJECT_DIR/.painel.pid"
LOG_FILE="$PROJECT_DIR/.painel.log"
PORTA="${TIMELAPSE_PORTA:-8765}"
URL="http://localhost:$PORTA"

if [[ -f "$PID_FILE" ]]; then
  RUNNING_PID="$(<"$PID_FILE")"
  if [[ "$RUNNING_PID" == <-> ]] && kill -0 "$RUNNING_PID" 2>/dev/null; then
    print -r -- "O painel já está ligado na porta $PORTA."
    exit 0
  fi
  rm -f "$PID_FILE"
fi

PYTHON="$(command -v python3)"
if [[ -z "$PYTHON" ]]; then
  print -u2 -r -- "Python 3 não encontrado neste Mac."
  exit 1
fi

cd "$PROJECT_DIR" || exit 1
nohup "$PYTHON" -m timelapse.servidor >>"$LOG_FILE" 2>&1 </dev/null &
SERVER_PID=$!
print -r -- "$SERVER_PID" >"$PID_FILE"

for _ in {1..60}; do
  if /usr/bin/curl -fsS "$URL/api/config" >/dev/null 2>&1; then
    print -r -- "Painel iniciado na porta $PORTA."
    exit 0
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    rm -f "$PID_FILE"
    print -u2 -r -- "O painel não conseguiu iniciar. Consulte .painel.log."
    exit 1
  fi
  sleep 0.2
done

print -r -- "Painel iniciado e ainda está preparando a primeira tela."
