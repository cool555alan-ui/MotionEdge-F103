#!/usr/bin/env python3
import json, re, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def version_values():
    firmware=re.search(r'APP_VERSION_STRING "([^"]+)"',(ROOT/"App/app_version.h").read_text()).group(1)
    package=re.search(r'version = "([^"]+)"',(ROOT/"host/pyproject.toml").read_text()).group(1)
    gateway=re.search(r'__version__ = "([^"]+)"',(ROOT/"host/motionctl/__init__.py").read_text()).group(1)
    return (ROOT/"VERSION").read_text().strip(),firmware,package,gateway
def main():
    values=version_values(); checks={"version_consistency":len(set(values))==1}
    required=["README.md","CHANGELOG.md","LICENSE","docs/config-persistence.md","docs/quick-start-v1.0.md",f"RELEASE_NOTES_v{values[0]}.md",".github/workflows/ci.yml",".github/workflows/release.yml"]
    checks["required_files"]=all((ROOT/x).is_file() for x in required)
    checks["debug_size"]=subprocess.run([sys.executable,str(ROOT/"tools/check-firmware-size.py"),str(ROOT/"build/Debug/MotionEdge-F103.elf")]).returncode==0
    checks["release_size"]=subprocess.run([sys.executable,str(ROOT/"tools/check-firmware-size.py"),str(ROOT/"build/Release/MotionEdge-F103.elf")]).returncode==0
    summaries=list((ROOT/"artifacts").glob("**/*summary.json"))
    core_fail=[]
    for path in summaries:
        try:data=json.loads(path.read_text(encoding="utf-8"))
        except Exception:continue
        if data.get("status") in {"FAIL","FAILED"}:core_fail.append(str(path.relative_to(ROOT)))
    checks["hardware_summaries_no_core_fail"]=not core_fail
    for key,value in checks.items():print(f"[{'PASS' if value else 'FAIL'}] {key}")
    if core_fail:print("Core FAIL summaries:",*core_fail,sep="\n")
    return 0 if all(checks.values()) else 1
if __name__=="__main__":sys.exit(main())
