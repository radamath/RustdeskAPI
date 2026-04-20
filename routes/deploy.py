"""Client deployment: quick scripts + RDGen custom client builder integration.

Quick Deploy  – generates PowerShell / Bash install scripts.
Custom Client – talks to rdgen.crayoneater.org to build branded RustDesk
               clients with embedded server config, logo, and company name.
"""

import os
import re
import textwrap
from urllib.parse import quote

import requests as http_requests
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from models import Setting, db
from routes.auth import admin_required, log_audit

bp = Blueprint("deploy", __name__, url_prefix="/admin/api/deploy")

RDGEN_DEFAULT_URL = "https://rdgen.crayoneater.org"

RE_BUILD_STATUS = re.compile(r"<span[^>]*>(.*?)</span>")
RE_CHECK_FILE = re.compile(
    r"window\.location\.replace\(\s*['\"]/check_for_file\?([^'\"]+)['\"]\s*\)",
    re.IGNORECASE,
)
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


def _rdgen_internal_enabled():
    return bool(current_app.config.get("RDGEN_INTERNAL_URL", "").strip())


def _rdgen_upstream():
    """Sunucunun RDGen'e bağlandığı adres (Docker içi veya harici)."""
    internal = (current_app.config.get("RDGEN_INTERNAL_URL") or "").strip().rstrip("/")
    if internal:
        return internal
    return _setting("deploy_rdgen_url", RDGEN_DEFAULT_URL).rstrip("/")


def _browser_api_base(req):
    pub = (current_app.config.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if pub:
        return pub
    return (req.url_root or "").rstrip("/")


def _rdgen_proxy_download_url(req, filename, uuid):
    base = _browser_api_base(req)
    return f"{base}/admin/api/deploy/rdgen-download?filename={quote(filename, safe='')}&uuid={quote(uuid, safe='')}"


def _build_rdgen_json(cfg, platform, version):
    """Build the JSON payload that rdgen expects as form-data POST."""
    exename = cfg.get("exename", "").strip() or "RustDesk"
    appname = cfg.get("appname", "").strip() or exename
    payload = {
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
    sh_secret = _setting("deploy_sh_secret")
    if sh_secret:
        payload["sh_secret_field"] = sh_secret
    return payload


def _download_links(req, filename, platform, uuid):
    """İndirme URL'leri: RDGen dahili kullanımdaysa API proxy; değilse doğrudan RDGen."""
    use_proxy = _rdgen_internal_enabled()
    if platform == "windows":
        pairs = [
            ("Windows EXE (64-bit)", f"{filename}.exe"),
            ("Windows MSI (64-bit)", f"{filename}.msi"),
        ]
    elif platform == "windows-x86":
        pairs = [("Windows EXE (32-bit)", f"{filename}.exe")]
    elif platform == "linux":
        pairs = []
        for arch in ("x86_64", "aarch64"):
            pairs.append((f"Linux DEB ({arch})", f"{filename}-{arch}.deb"))
            pairs.append((f"Linux RPM ({arch})", f"{filename}-{arch}.rpm"))
        pairs.append(("Linux AppImage (x86_64)", f"{filename}-x86_64.AppImage"))
    elif platform == "android":
        pairs = [("Android APK (arm64)", f"{filename}-aarch64.apk")]
    elif platform == "macos":
        pairs = [
            ("macOS DMG (Apple Silicon)", f"{filename}-aarch64.dmg"),
            ("macOS DMG (Intel)", f"{filename}-x86_64.dmg"),
        ]
    else:
        pairs = []

    links = []
    upstream = _rdgen_upstream()
    for label, fn in pairs:
        if use_proxy:
            url = _rdgen_proxy_download_url(req, fn, uuid)
        else:
            url = f"{upstream}/download?filename={quote(fn, safe='')}&uuid={quote(uuid, safe='')}"
        links.append({"label": label, "url": url})
    return links


# ── Config Endpoints ─────────────────────────────────────────────────

@bp.route("/config", methods=["GET"])
@admin_required
def get_config():
    cfg = _get_deploy_config()
    internal = _rdgen_internal_enabled()
    cfg["rdgen_internal"] = internal
    if internal:
        cfg["rdgen_url"] = ""
    else:
        cfg["rdgen_url"] = _setting("deploy_rdgen_url", RDGEN_DEFAULT_URL).rstrip("/")
    cfg["sh_secret"] = _setting("deploy_sh_secret")
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
        "sh_secret": "deploy_sh_secret",
    }
    for short, db_key in field_map.items():
        if short in data:
            if short == "rdgen_url" and _rdgen_internal_enabled():
                continue
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
    base_url = _rdgen_upstream()

    try:
        resp = http_requests.post(
            f"{base_url}/generator",
            data=payload,
            timeout=(20, 180),
            headers={"User-Agent": "RustdeskAPI-deploy/1.0"},
        )
    except http_requests.exceptions.ConnectionError as e:
        return jsonify({
            "error": (
                f"RDGen'e TCP ile bağlanılamadı ({base_url}). "
                "rustdesk-api ile rdgen aynı Docker ağında mı, RDGEN_INTERNAL_URL doğru mu "
                "(örn. http://rdgen:8000), rdgen konteyneri ayakta mı kontrol edin."
            ),
            "detail": str(e),
        }), 502
    except http_requests.exceptions.Timeout:
        return jsonify({
            "error": "RDGen yanıt vermedi (zaman aşımı 180s). Sunucu yükü veya GitHub runner kuyruğu olabilir.",
        }), 502
    except Exception as e:
        return jsonify({"error": f"RDGen sunucusuna bağlanılamadı: {e}"}), 502

    if resp.status_code == 401:
        return jsonify({
            "error": (
                "RDGen 401: GitHub token (GHBEARER) geçersiz veya süresi dolmuş olabilir; "
                "GENURL panel adresinizle uyumlu olmalı. rdgen konteyner ortam değişkenlerini kontrol edin."
            ),
        }), 502

    if resp.status_code < 200 or resp.status_code >= 300:
        detail = ""
        try:
            j = resp.json()
            detail = j.get("error") or j.get("message") or str(j)
        except Exception:
            detail = (resp.text or "")[:800]
        return jsonify(
            {
                "error": f"RDGen hatası (HTTP {resp.status_code}): {detail or 'yanıt gövdesi yok'}",
                "upstream": base_url,
            }
        ), 502

    html = resp.text
    status_match = RE_BUILD_STATUS.search(html)
    file_match = RE_CHECK_FILE.search(html)

    if not file_match:
        if "application/json" in (resp.headers.get("Content-Type") or "").lower():
            try:
                j = resp.json()
                return jsonify({"error": f"RDGen: {j.get('error', j)}"}), 502
            except Exception:
                pass
        return jsonify(
            {
                "error": "RDGen yanıtı ayrıştırılamadı (check_for_file yok). "
                "RDGen imajını rdgen-patched ile yeniden build edin veya RDGen loglarına bakın.",
            }
        ), 502

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

    links = _download_links(request, filename, build_platform, uuid)

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

    base_url = _rdgen_upstream()
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

    links = _download_links(request, filename, platform, uuid)

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

    links = _download_links(request, filename, platform, uuid)
    return jsonify({"downloads": links, "uuid": uuid, "filename": filename, "platform": platform})


@bp.route("/rdgen-download", methods=["GET"])
@admin_required
def rdgen_download_proxy():
    """RDGen /download uç noktasını admin oturumu arkasında proxy'ler (tarayıcı RDGen'e gitmez)."""
    qs = request.query_string.decode("utf-8")
    if not qs:
        return jsonify({"error": "Geçersiz istek"}), 400
    upstream = _rdgen_upstream()
    url = f"{upstream}/download?{qs}"
    try:
        upstream_resp = http_requests.get(url, stream=True, timeout=600)
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    if upstream_resp.status_code < 200 or upstream_resp.status_code >= 300:
        return jsonify({"error": f"RDGen: HTTP {upstream_resp.status_code}"}), upstream_resp.status_code

    excluded = {"content-encoding", "transfer-encoding", "connection"}
    pass_headers = [
        (k, v)
        for k, v in upstream_resp.headers.items()
        if k.lower() not in excluded
    ]

    def generate():
        for chunk in upstream_resp.iter_content(chunk_size=65536):
            if chunk:
                yield chunk

    return Response(
        stream_with_context(generate()),
        status=upstream_resp.status_code,
        headers=dict(pass_headers),
    )


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
