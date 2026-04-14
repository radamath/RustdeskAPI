"""Client deployment: quick scripts + RDGen custom client builder integration.

Quick Deploy  – generates PowerShell / Bash install scripts.
Custom Client – talks to rdgen.crayoneater.org to build branded RustDesk
               clients with embedded server config, logo, and company name.
"""

import os
import re
import textwrap

import requests as http_requests
from flask import Blueprint, Response, jsonify, request

from models import Setting, db
from routes.auth import admin_required, log_audit

bp = Blueprint("deploy", __name__, url_prefix="/admin/api/deploy")

RDGEN_DEFAULT_URL = "https://rdgen.crayoneater.org"

RE_BUILD_STATUS = re.compile(r"<span[^>]*>(.*?)</span>")
RE_CHECK_FILE = re.compile(r"window\.location\.replace\('\/check_for_file\?(.*?)'\);")
RE_PAGE_TITLE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE)


# ── Helpers ──────────────────────────────────────────────────────────

def _read_public_key():
    from flask import current_app
    rd_db_path = current_app.config["RUSTDESK_DB_PATH"]
    rd_dir = os.path.dirname(rd_db_path) if rd_db_path else ""
    key_path = os.path.join(rd_dir, "id_ed25519.pub") if rd_dir else ""
    if key_path and os.path.isfile(key_path):
        with open(key_path, "r") as f:
            return f.read().strip()
    return ""


def _setting(key, default=""):
    s = db.session.get(Setting, key)
    return s.value if s else default


def _set_setting(key, value):
    s = db.session.get(Setting, key)
    if s:
        s.value = str(value)
    else:
        db.session.add(Setting(key=key, value=str(value)))


def _get_deploy_config():
    return {
        "host": _setting("deploy_host"),
        "relay": _setting("deploy_relay"),
        "api": _setting("deploy_api"),
        "key": _read_public_key(),
        "appname": _setting("deploy_appname"),
        "exename": _setting("deploy_exename"),
        "compname": _setting("deploy_compname"),
        "iconbase64": _setting("deploy_icon"),
        "logobase64": _setting("deploy_logo"),
    }


def _build_config_string(cfg):
    return (
        f'{cfg["host"]},'
        f'key={cfg["key"]},'
        f'api={cfg["api"]},'
        f'relay={cfg["relay"]}'
    )


def _rdgen_base():
    return _setting("deploy_rdgen_url", RDGEN_DEFAULT_URL).rstrip("/")


def _build_rdgen_json(cfg, platform, version):
    """Build the JSON payload that rdgen expects as form-data POST."""
    exename = cfg.get("exename", "").strip() or "RustDesk"
    appname = cfg.get("appname", "").strip() or exename
    return {
        "platform": platform,
        "version": version,
        "delayFix": "on",
        "exename": exename,
        "appname": appname,
        "direction": "both",
        "installation": "installationY",
        "settings": "settingsY",
        "androidappid": "",
        "serverIP": cfg.get("host", ""),
        "key": cfg.get("key", ""),
        "apiServer": cfg.get("api", ""),
        "urlLink": "",
        "downloadLink": "",
        "compname": cfg.get("compname", ""),
        "passApproveMode": "password-click",
        "permanentPassword": "",
        "iconbase64": cfg.get("iconbase64", ""),
        "logobase64": cfg.get("logobase64", ""),
        "privacybase64": "",
        "iconfile": {},
        "logofile": {},
        "privacyfile": {},
        "theme": "system",
        "themeDorO": "default",
        "permissionsDorO": "default",
        "permissionsType": "custom",
        "enableKeyboard": "on",
        "enableClipboard": "on",
        "enableFileTransfer": "on",
        "enableAudio": "on",
        "enableTCP": "on",
        "enableRemoteRestart": "on",
        "enableRecording": "on",
        "enableBlockingInput": "on",
        "enablePrinter": "on",
        "enableCamera": "on",
        "enableTerminal": "on",
        "removeWallpaper": "on",
        "defaultManual": "",
        "overrideManual": "",
        "denyLan": False,
        "enableDirectIP": False,
        "autoClose": False,
        "hidecm": False,
        "enableRemoteModi": False,
        "cycleMonitor": False,
        "xOffline": False,
        "removeNewVersionNotif": False,
    }


def _download_links(base_url, filename, platform, uuid):
    common = f"{base_url}/download?"
    links = []
    if platform == "windows":
        links.append({"label": "Windows EXE (64-bit)", "url": f"{common}filename={filename}.exe&uuid={uuid}"})
        links.append({"label": "Windows MSI (64-bit)", "url": f"{common}filename={filename}.msi&uuid={uuid}"})
    elif platform == "windows-x86":
        links.append({"label": "Windows EXE (32-bit)", "url": f"{common}filename={filename}.exe&uuid={uuid}"})
    elif platform == "linux":
        for arch in ("x86_64", "aarch64"):
            links.append({"label": f"Linux DEB ({arch})", "url": f"{common}filename={filename}-{arch}.deb&uuid={uuid}"})
            links.append({"label": f"Linux RPM ({arch})", "url": f"{common}filename={filename}-{arch}.rpm&uuid={uuid}"})
        links.append({"label": "Linux AppImage (x86_64)", "url": f"{common}filename={filename}-x86_64.AppImage&uuid={uuid}"})
    elif platform == "android":
        links.append({"label": "Android APK (arm64)", "url": f"{common}filename={filename}-aarch64.apk&uuid={uuid}"})
    elif platform == "macos":
        links.append({"label": "macOS DMG (Apple Silicon)", "url": f"{common}filename={filename}-aarch64.dmg&uuid={uuid}"})
        links.append({"label": "macOS DMG (Intel)", "url": f"{common}filename={filename}-x86_64.dmg&uuid={uuid}"})
    return links


# ── Config Endpoints ─────────────────────────────────────────────────

@bp.route("/config", methods=["GET"])
@admin_required
def get_config():
    cfg = _get_deploy_config()
    cfg["rdgen_url"] = _rdgen_base()
    cfg["build_uuid"] = _setting("deploy_build_uuid")
    cfg["build_filename"] = _setting("deploy_build_filename")
    cfg["build_platform"] = _setting("deploy_build_platform")
    return jsonify(cfg)


@bp.route("/config", methods=["PUT"])
@admin_required
def update_config():
    data = request.get_json(silent=True) or {}
    field_map = {
        "host": "deploy_host",
        "relay": "deploy_relay",
        "api": "deploy_api",
        "appname": "deploy_appname",
        "exename": "deploy_exename",
        "compname": "deploy_compname",
        "iconbase64": "deploy_icon",
        "logobase64": "deploy_logo",
        "rdgen_url": "deploy_rdgen_url",
    }
    for short, db_key in field_map.items():
        if short in data:
            _set_setting(db_key, data[short])
    db.session.commit()
    log_audit("deploy_config", "Dağıtım ayarları güncellendi")
    return jsonify({"ok": True})


# ── RDGen Build Endpoints ────────────────────────────────────────────

@bp.route("/build", methods=["POST"])
@admin_required
def start_build():
    data = request.get_json(silent=True) or {}
    platform = data.get("platform", "windows")
    version = data.get("version", "1.4.6")

    cfg = _get_deploy_config()
    if not cfg["host"] or not cfg["key"]:
        return jsonify({"error": "Sunucu adresi ve public key ayarlanmalı"}), 400

    payload = _build_rdgen_json(cfg, platform, version)
    base_url = _rdgen_base()

    try:
        resp = http_requests.post(
            f"{base_url}/generator",
            data=payload,
            timeout=60,
        )
    except Exception as e:
        return jsonify({"error": f"RDGen sunucusuna bağlanılamadı: {e}"}), 502

    if resp.status_code < 200 or resp.status_code >= 300:
        return jsonify({"error": f"RDGen hatası: HTTP {resp.status_code}"}), 502

    html = resp.text
    status_match = RE_BUILD_STATUS.search(html)
    file_match = RE_CHECK_FILE.search(html)

    if not file_match:
        return jsonify({"error": "RDGen yanıtı ayrıştırılamadı. Sunucu ayarlarını kontrol edin."}), 502

    query_str = file_match.group(1)
    params = dict(p.split("=", 1) for p in query_str.split("&") if "=" in p)
    filename = params.get("filename", "")
    uuid = params.get("uuid", "")
    build_platform = params.get("platform", platform)

    _set_setting("deploy_build_uuid", uuid)
    _set_setting("deploy_build_filename", filename)
    _set_setting("deploy_build_platform", build_platform)
    db.session.commit()

    stage = status_match.group(1) if status_match else "Başlatılıyor..."

    links = _download_links(base_url, filename, build_platform, uuid)

    log_audit("deploy_build", f"Özel client build başlatıldı: {platform} v{version}")
    return jsonify({
        "status": "generating",
        "stage": stage,
        "uuid": uuid,
        "filename": filename,
        "platform": build_platform,
        "downloads": links,
    })


@bp.route("/status", methods=["GET"])
@admin_required
def build_status():
    uuid = _setting("deploy_build_uuid")
    filename = _setting("deploy_build_filename")
    platform = _setting("deploy_build_platform")

    if not uuid or not filename:
        return jsonify({"status": "idle", "stage": "Aktif build yok"})

    base_url = _rdgen_base()
    check_url = f"{base_url}/check_for_file?filename={filename}&uuid={uuid}&platform={platform}"

    try:
        resp = http_requests.get(check_url, timeout=30)
    except Exception as e:
        return jsonify({"status": "error", "stage": f"RDGen bağlantı hatası: {e}"}), 502

    html = resp.text
    title_match = RE_PAGE_TITLE.search(html)
    title = (title_match.group(1) if title_match else "").lower()

    status_match = RE_BUILD_STATUS.search(html)
    stage = status_match.group(1) if status_match else ""

    links = _download_links(base_url, filename, platform, uuid)

    if "generated" in title:
        if "Error: No file generated" in html:
            return jsonify({"status": "error", "stage": "Build başarısız: dosya oluşturulamadı", "downloads": []})
        return jsonify({"status": "completed", "stage": "Tamamlandı", "downloads": links})

    if "generating" in title:
        return jsonify({"status": "generating", "stage": stage, "downloads": links})

    return jsonify({"status": "unknown", "stage": stage or title, "downloads": links})


@bp.route("/downloads", methods=["GET"])
@admin_required
def get_downloads():
    uuid = _setting("deploy_build_uuid")
    filename = _setting("deploy_build_filename")
    platform = _setting("deploy_build_platform")

    if not uuid or not filename:
        return jsonify({"downloads": []})

    links = _download_links(_rdgen_base(), filename, platform, uuid)
    return jsonify({"downloads": links, "uuid": uuid, "filename": filename, "platform": platform})


# ── Quick Deploy Script Endpoints (preserved) ────────────────────────

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
    fname = f"rustdesk-install-{platform}{ext}"

    return Response(
        script,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
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
        if (-not $downloadUrl) {{ Write-Host "HATA: Indirme baglantisi bulunamadi." -ForegroundColor Red; Exit 1 }}

        if (!(Test-Path C:\\Temp)) {{ New-Item -ItemType Directory -Force -Path C:\\Temp | Out-Null }}
        Set-Location C:\\Temp
        Write-Host "RustDesk indiriliyor..." -ForegroundColor Cyan
        Invoke-WebRequest $downloadUrl -OutFile "rustdesk.exe"
        Write-Host "Kurulum yapiliyor..." -ForegroundColor Cyan
        Start-Process .\\rustdesk.exe --silent-install -Wait
        Start-Sleep -Seconds 20

        $svc = Get-Service -Name 'RustDesk' -ErrorAction SilentlyContinue
        if ($null -eq $svc) {{ Set-Location "$env:ProgramFiles\\RustDesk"; Start-Process .\\rustdesk.exe --install-service; Start-Sleep -Seconds 20 }}

        Set-Location "$env:ProgramFiles\\RustDesk"
        $rustdesk_id = .\\rustdesk.exe --get-id
        .\\rustdesk.exe --config $rustdesk_cfg
        .\\rustdesk.exe --password $rustdesk_pw
        Start-Sleep -Seconds 3
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

        if [ "$EUID" -ne 0 ]; then echo "Root olarak calistirin."; exit 1; fi
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
        else echo "Desteklenmeyen dagitim."; exit 1; fi
        rustdesk_id=$(rustdesk --get-id)
        rustdesk --config "$rustdesk_cfg"
        rustdesk --password "$rustdesk_pw"
        systemctl restart rustdesk 2>/dev/null || true
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
        [ "$UID" -eq 0 ] || exec sudo bash "$0" "$@"
        mount_point="/Volumes/RustDesk"
        LATEST_URL=$(curl -sL -o /dev/null -w '%{{url_effective}}' https://github.com/rustdesk/rustdesk/releases/latest)
        VERSION=$(echo "$LATEST_URL" | grep -oP '[\\d.]+$')
        if [ "$(arch)" = "arm64" ]; then DMG="rustdesk-$VERSION.aarch64.dmg"; else DMG="rustdesk-$VERSION.x86_64.dmg"; fi
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
        echo "===================================="
        echo "  ID    : $rustdesk_id"
        echo "  Sifre : $rustdesk_pw"
        echo "===================================="
    """)
