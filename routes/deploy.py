"""Client deployment script generator.

Produces ready-to-run PowerShell / Bash scripts that download the latest
RustDesk client, install it silently, and configure it to connect to this
self-hosted server.
"""

import os
import textwrap

from flask import Blueprint, Response, jsonify, request

from models import Setting, db
from routes.auth import admin_required, log_audit

bp = Blueprint("deploy", __name__, url_prefix="/admin/api/deploy")


def _read_public_key():
    from flask import current_app
    rd_db_path = current_app.config["RUSTDESK_DB_PATH"]
    rd_dir = os.path.dirname(rd_db_path) if rd_db_path else ""
    key_path = os.path.join(rd_dir, "id_ed25519.pub") if rd_dir else ""
    if key_path and os.path.isfile(key_path):
        with open(key_path, "r") as f:
            return f.read().strip()
    return ""


def _get_deploy_config():
    host = (db.session.get(Setting, "deploy_host") or Setting(value="")).value
    relay = (db.session.get(Setting, "deploy_relay") or Setting(value="")).value
    api_url = (db.session.get(Setting, "deploy_api") or Setting(value="")).value
    key = _read_public_key()
    return {"host": host, "relay": relay, "api": api_url, "key": key}


def _build_config_string(cfg):
    """Build the config string RustDesk accepts via --config."""
    return (
        f'{cfg["host"]},'
        f'key={cfg["key"]},'
        f'api={cfg["api"]},'
        f'relay={cfg["relay"]}'
    )


# ── Endpoints ────────────────────────────────────────────────────────

@bp.route("/config", methods=["GET"])
@admin_required
def get_config():
    return jsonify(_get_deploy_config())


@bp.route("/config", methods=["PUT"])
@admin_required
def update_config():
    data = request.get_json(silent=True) or {}
    for field in ("deploy_host", "deploy_relay", "deploy_api"):
        short = field.replace("deploy_", "")
        if short in data:
            s = db.session.get(Setting, field)
            if s:
                s.value = str(data[short])
            else:
                s = Setting(key=field, value=str(data[short]))
                db.session.add(s)
    db.session.commit()
    log_audit("deploy_config", "Dağıtım ayarları güncellendi")
    return jsonify({"ok": True})


@bp.route("/script/<platform>", methods=["GET"])
@admin_required
def generate_script(platform):
    cfg = _get_deploy_config()
    if not cfg["host"] or not cfg["key"]:
        return jsonify({"error": "Sunucu adresi ve public key gerekli"}), 400

    config_str = _build_config_string(cfg)
    password = request.args.get("password", "random")

    generators = {
        "windows": _windows_script,
        "linux": _linux_script,
        "macos": _macos_script,
    }
    gen = generators.get(platform)
    if not gen:
        return jsonify({"error": "Geçersiz platform"}), 400

    script = gen(config_str, password)
    ext = ".ps1" if platform == "windows" else ".sh"
    filename = f"rustdesk-install-{platform}{ext}"

    return Response(
        script,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Script Templates ─────────────────────────────────────────────────

def _windows_script(config_str, password):
    pw_line = (
        '$rustdesk_pw = (-join ((65..90) + (97..122) | Get-Random -Count 12 | % {[char]$_}))'
        if password == "random"
        else f'$rustdesk_pw = "{password}"'
    )
    return textwrap.dedent(f"""\
        $ErrorActionPreference = 'SilentlyContinue'

        {pw_line}
        $rustdesk_cfg = "{config_str}"

        # --- Asagisini duzenlemenize gerek yok ---

        if (-Not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
            Start-Process PowerShell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `\\"cd '$pwd'; & '$PSCommandPath';`\\""
            Exit
        }}

        function Get-LatestRustDesk {{
            $page = Invoke-WebRequest -Uri 'https://github.com/rustdesk/rustdesk/releases/latest' -UseBasicParsing
            $link = ($page.Links | Where-Object {{ $_.href -match '/rustdesk/rustdesk/releases/download/[\\d.]+/rustdesk-[\\d.]+-x86_64\\.exe$' }} | Select-Object -First 1).href
            if ($link -and -not $link.StartsWith('http')) {{ $link = "https://github.com$link" }}
            return $link
        }}

        $downloadUrl = Get-LatestRustDesk
        if (-not $downloadUrl) {{
            Write-Host "HATA: RustDesk indirme baglantisi bulunamadi." -ForegroundColor Red
            Exit 1
        }}

        if (!(Test-Path C:\\Temp)) {{ New-Item -ItemType Directory -Force -Path C:\\Temp | Out-Null }}
        Set-Location C:\\Temp

        Write-Host "RustDesk indiriliyor..." -ForegroundColor Cyan
        Invoke-WebRequest $downloadUrl -OutFile "rustdesk.exe"

        Write-Host "Sessiz kurulum yapiliyor..." -ForegroundColor Cyan
        Start-Process .\\rustdesk.exe --silent-install -Wait
        Start-Sleep -Seconds 20

        $svcName = 'RustDesk'
        $svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
        if ($null -eq $svc) {{
            Set-Location "$env:ProgramFiles\\RustDesk"
            Start-Process .\\rustdesk.exe --install-service
            Start-Sleep -Seconds 20
        }}

        Set-Location "$env:ProgramFiles\\RustDesk"

        $rustdesk_id = .\\rustdesk.exe --get-id
        .\\rustdesk.exe --config $rustdesk_cfg
        .\\rustdesk.exe --password $rustdesk_pw

        Start-Sleep -Seconds 3

        Write-Host ""
        Write-Host "====================================" -ForegroundColor Green
        Write-Host "  RustDesk Kurulum Tamamlandi!" -ForegroundColor Green
        Write-Host "====================================" -ForegroundColor Green
        Write-Host "  ID    : $rustdesk_id" -ForegroundColor Yellow
        Write-Host "  Sifre : $rustdesk_pw" -ForegroundColor Yellow
        Write-Host "====================================" -ForegroundColor Green
    """)


def _linux_script(config_str, password):
    pw_line = (
        "rustdesk_pw=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 12 | head -n 1)"
        if password == "random"
        else f'rustdesk_pw="{password}"'
    )
    return textwrap.dedent(f"""\
        #!/bin/bash
        set -e

        {pw_line}
        rustdesk_cfg="{config_str}"

        # --- Asagisini duzenlemenize gerek yok ---

        if [ "$EUID" -ne 0 ]; then
            echo "Bu script root olarak calistirilmalidir."
            exit 1
        fi

        echo "RustDesk indiriliyor..."

        LATEST_URL=$(curl -sL -o /dev/null -w '%{{url_effective}}' https://github.com/rustdesk/rustdesk/releases/latest)
        VERSION=$(echo "$LATEST_URL" | grep -oP '[\\d.]+$')

        if [ -f /etc/debian_version ]; then
            PKG="rustdesk-$VERSION-x86_64.deb"
            curl -L "https://github.com/rustdesk/rustdesk/releases/download/$VERSION/$PKG" -o "/tmp/$PKG"
            apt-get install -fy "/tmp/$PKG"
        elif [ -f /etc/redhat-release ]; then
            PKG="rustdesk-$VERSION-0.x86_64.rpm"
            curl -L "https://github.com/rustdesk/rustdesk/releases/download/$VERSION/$PKG" -o "/tmp/$PKG"
            yum localinstall -y "/tmp/$PKG"
        else
            echo "Desteklenmeyen Linux dagitimi. Lutfen manuel kurun."
            exit 1
        fi

        rustdesk_id=$(rustdesk --get-id)
        rustdesk --config "$rustdesk_cfg"
        rustdesk --password "$rustdesk_pw"

        systemctl restart rustdesk 2>/dev/null || true

        echo ""
        echo "===================================="
        echo "  RustDesk Kurulum Tamamlandi!"
        echo "===================================="
        echo "  ID    : $rustdesk_id"
        echo "  Sifre : $rustdesk_pw"
        echo "===================================="
    """)


def _macos_script(config_str, password):
    pw_line = (
        'rustdesk_pw=$(openssl rand -hex 6)'
        if password == "random"
        else f'rustdesk_pw="{password}"'
    )
    return textwrap.dedent(f"""\
        #!/bin/bash
        set -e

        {pw_line}
        rustdesk_cfg="{config_str}"

        # --- Asagisini duzenlemenize gerek yok ---

        [ "$UID" -eq 0 ] || exec sudo bash "$0" "$@"

        mount_point="/Volumes/RustDesk"

        echo "RustDesk indiriliyor..."

        LATEST_URL=$(curl -sL -o /dev/null -w '%{{url_effective}}' https://github.com/rustdesk/rustdesk/releases/latest)
        VERSION=$(echo "$LATEST_URL" | grep -oP '[\\d.]+$')

        if [ "$(arch)" = "arm64" ]; then
            DMG="rustdesk-$VERSION.aarch64.dmg"
        else
            DMG="rustdesk-$VERSION.x86_64.dmg"
        fi

        curl -L "https://github.com/rustdesk/rustdesk/releases/download/$VERSION/$DMG" -o "/tmp/$DMG"

        hdiutil attach "/tmp/$DMG" -mountpoint "$mount_point" > /dev/null 2>&1
        cp -R "$mount_point/RustDesk.app" "/Applications/"
        hdiutil detach "$mount_point" > /dev/null 2>&1

        cd /Applications/RustDesk.app/Contents/MacOS/
        rustdesk_id=$(./RustDesk --get-id)

        ./RustDesk --server &
        sleep 2
        ./RustDesk --config "$rustdesk_cfg"
        ./RustDesk --password "$rustdesk_pw"

        pkill RustDesk 2>/dev/null || true
        sleep 1
        open -n /Applications/RustDesk.app

        echo ""
        echo "===================================="
        echo "  RustDesk Kurulum Tamamlandi!"
        echo "===================================="
        echo "  ID    : $rustdesk_id"
        echo "  Sifre : $rustdesk_pw"
        echo "===================================="
    """)
