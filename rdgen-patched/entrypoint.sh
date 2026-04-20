#!/bin/sh
# Named volume'lar root sahipli gelir; RDGen gunicorn user ile temp_zips'e yazamaz.
set -e
run_as_user() {
  if command -v gosu >/dev/null 2>&1; then
    exec gosu user "$@"
  fi
  if command -v su-exec >/dev/null 2>&1; then
    exec su-exec user "$@"
  fi
  echo "entrypoint: gosu/su-exec yok, root olarak devam (beklenmeyen)" >&2
  exec "$@"
}

if [ "$(id -u)" = "0" ]; then
  for d in /opt/rdgen/temp_zips /opt/rdgen/exe /opt/rdgen/png; do
    mkdir -p "$d"
    if chown -R user:user "$d" 2>/dev/null; then
      :
    else
      chmod -R 777 "$d" 2>/dev/null || true
    fi
  done
  run_as_user "$@"
fi
exec "$@"
