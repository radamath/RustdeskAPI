#!/usr/bin/env python3
"""
1) GitHub 204 + boş gövde → response.json() patlamasın.
2) GithubRun(id=...) — modelde id IntegerField PK ve AutoField değil; verilmezse save() 500 döner.
"""
import re
from pathlib import Path

VIEWS = Path("/opt/rdgen/rdgenerator/views.py")
text = VIEWS.read_text(encoding="utf-8")

# --- Import Max ---
if "from django.db.models import Q, Max" not in text:
    text = text.replace(
        "from django.db.models import Q\n",
        "from django.db.models import Q, Max\n",
        1,
    )

# --- 204 / boş JSON ---
pattern_json = re.compile(
    r"(?m)^(?P<i1>[ \t]+)if response\.status_code == 204 or response\.status_code == 200:\n"
    r"(?P<i2>[ \t]+)github_data = response\.json\(\)\n"
    r"(?P=i2)print\(github_data\)"
)


def repl_json(m: re.Match) -> str:
    i1 = m.group("i1")
    i2 = m.group("i2")
    unit = i2[len(i1) :] if i2.startswith(i1) and len(i2) > len(i1) else "    "
    i3 = i2 + unit
    i4 = i3 + unit
    return (
        f"{i1}if response.status_code == 204 or response.status_code == 200:\n"
        f"{i2}github_data = {{}}\n"
        f"{i2}if response.content and response.content.strip():\n"
        f"{i3}try:\n"
        f"{i4}github_data = response.json()\n"
        f"{i3}except ValueError:\n"
        f"{i4}github_data = {{}}\n"
        f"{i2}print(github_data)"
    )


text, n_json = pattern_json.subn(repl_json, text, count=1)
if n_json != 1:
    raise SystemExit(
        "apply_patch: github_data = response.json() bloğu bulunamadı (imaj sürümü değişmiş olabilir)"
    )

# --- GithubRun primary key ---
pattern_run = re.compile(
    r"(?m)^(?P<ind>[ \t]+)new_github_run = GithubRun\(\n"
    r"(?P=ind)(?P<sp>[ \t]+)uuid=myuuid,\n"
    r"(?P=ind)(?P=sp)status=\"Starting generator\.\.\.please wait\"\n"
    r"(?P=ind)\)"
)


def repl_run(m: re.Match) -> str:
    ind = m.group("ind")
    sp = m.group("sp")
    return (
        f"{ind}_rdgen_next_pk = (GithubRun.objects.aggregate(_rdgen_m=Max('id'))['_rdgen_m'] or 0) + 1\n"
        f"{ind}new_github_run = GithubRun(\n"
        f"{ind}{sp}id=_rdgen_next_pk,\n"
        f"{ind}{sp}uuid=myuuid,\n"
        f"{ind}{sp}status=\"Starting generator...please wait\"\n"
        f"{ind})"
    )


text, n_run = pattern_run.subn(repl_run, text)
if n_run < 1:
    raise SystemExit("apply_patch: new_github_run = GithubRun(...) bloğu bulunamadı")

VIEWS.write_text(text, encoding="utf-8")
print(f"apply_patch: tamam (204-json:1, GithubRun.id:{n_run})")
