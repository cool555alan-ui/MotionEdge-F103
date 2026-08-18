#!/usr/bin/env python3
"""Build and verify the auditable v1.0.0 release bundle."""
import hashlib,json,os,shutil,subprocess,sys,tempfile,venv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; VERSION=(ROOT/"VERSION").read_text().strip(); OUT=ROOT/f"dist/release/v{VERSION}"
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    if OUT.exists():shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    base=ROOT/"build/Release/MotionEdge-F103"
    objcopy=shutil.which("arm-none-eabi-objcopy")
    if objcopy is None:raise RuntimeError("arm-none-eabi-objcopy not found")
    subprocess.run([objcopy,"-O","ihex",str(base.with_suffix(".elf")),str(base.with_suffix(".hex"))],check=True)
    subprocess.run([objcopy,"-O","binary",str(base.with_suffix(".elf")),str(base.with_suffix(".bin"))],check=True)
    for ext in ("hex","bin","elf"):shutil.copy2(base.with_suffix(f".{ext}"),OUT/f"motionedge-f103-v{VERSION}.{ext}")
    subprocess.run([sys.executable,"-m","build",str(ROOT/"host"),"--outdir",str(OUT)],check=True)
    shutil.copy2(ROOT/"config/motionedge-gateway.example.toml",OUT/"motionedge-gateway.example.toml")
    shutil.copy2(ROOT/"node-red/flows/motionedge-phase07.json",OUT/"motionedge-node-red-v1.0.0.json")
    shutil.copy2(ROOT/"docs/quick-start-v1.0.md",OUT/"QUICKSTART.md")
    shutil.copy2(ROOT/"RELEASE_NOTES_v1.0.0.md",OUT/"RELEASE_NOTES.md")
    commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    manifest={"project":"MotionEdge-F103","version":VERSION,"git_commit":commit,"build_type":"Release","config_schema":1,
              "flash":{"physical_bytes":65536,"reserved_bytes":2048,"application_limit_bytes":63488,"slot_a":"0x0800F800","slot_b":"0x0800FC00","page_bytes":1024},
              "ram_limit_bytes":18944,"artifacts":sorted(p.name for p in OUT.iterdir())}
    (OUT/"release-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    files=sorted(p for p in OUT.iterdir() if p.name!="SHA256SUMS.txt")
    (OUT/"SHA256SUMS.txt").write_text("".join(f"{sha(p)}  {p.name}\n" for p in files),encoding="utf-8")
    wheel=next(OUT.glob("*.whl"))
    with tempfile.TemporaryDirectory() as directory:
        env=Path(directory)/"venv";venv.EnvBuilder(with_pip=True).create(env)
        python=env/("Scripts/python.exe" if os.name=="nt" else "bin/python")
        subprocess.run([str(python),"-m","pip","install","--no-deps",str(wheel)],check=True,stdout=subprocess.DEVNULL)
        output=subprocess.check_output([str(python),"-m","motionctl","--version"],text=True).strip()
        if output!=VERSION:raise RuntimeError(f"wheel version mismatch: {output}")
        subprocess.run([str(python),"-m","motionctl","--help"],check=True,stdout=subprocess.DEVNULL)
    print(f"Release bundle: {OUT}")
if __name__=="__main__":main()
