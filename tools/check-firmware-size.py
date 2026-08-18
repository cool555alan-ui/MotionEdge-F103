#!/usr/bin/env python3
"""Fail when firmware exceeds the official STM32F103C8 application/RAM budget."""
import argparse, re, subprocess, sys
from pathlib import Path

PHYSICAL_FLASH=65536
RESERVED_CONFIG=2048
APP_FLASH_LIMIT=PHYSICAL_FLASH-RESERVED_CONFIG
RAM_LIMIT=18944
CONFIG_START=0x0800F800

def tool(name):
    from shutil import which
    found=which(name)
    if found:return found
    roots=list((Path.home()/"AppData/Local/stm32cube/bundles/gcc").glob(f"*/bin/{name}.exe"))
    if not roots:raise RuntimeError(f"{name} not found")
    return str(sorted(roots)[-1])

def main():
    parser=argparse.ArgumentParser();parser.add_argument("elf",type=Path);args=parser.parse_args()
    output=subprocess.check_output([tool("arm-none-eabi-size"),str(args.elf)],text=True)
    values=[int(x) for x in re.findall(r"\d+",output.splitlines()[-1])[:3]]
    ram=values[1]+values[2]
    sections=subprocess.check_output([tool("arm-none-eabi-objdump"),"-h",str(args.elf)],text=True)
    highest=0;flash=0
    lines=sections.splitlines()
    for index,line in enumerate(lines):
        match=re.match(r"\s*\d+\s+(\S+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)",line)
        flags=lines[index+1] if index+1<len(lines) else ""
        if match and match.group(1)!=".config_slots" and "LOAD" in flags:
            size=int(match.group(2),16);lma=int(match.group(4),16)
            if 0x08000000<=lma<0x20000000:
                highest=max(highest,lma+size);flash+=size
    ok=flash<=APP_FLASH_LIMIT and ram<=RAM_LIMIT and highest<=CONFIG_START
    print(f"Flash={flash}/{APP_FLASH_LIMIT} remaining={APP_FLASH_LIMIT-flash}; RAM={ram}/{RAM_LIMIT} remaining={RAM_LIMIT-ram}; image_end=0x{highest:08X}; config_start=0x{CONFIG_START:08X}")
    return 0 if ok else 1
if __name__=="__main__":sys.exit(main())
