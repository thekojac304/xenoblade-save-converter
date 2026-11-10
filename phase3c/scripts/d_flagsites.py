"""Part D: every call of the Wii flag setter 0x8009D9F0 / getter candidates, with the instruction that forms the flag id
(r3) - immediates and base+index forms in the high 1-bit range. Read-only."""
import os, re, subprocess, sys
ROOT = r"C:\Dev\XC_Wii_to_DE_Research"
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ppc
d = open(os.path.join(ROOT, "exe", "wii", "main.dol"), "rb").read()
def xrefs(t):
    out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "ppc.py"), os.path.join(ROOT, "exe", "wii", "main.dol"), "xref", hex(t)[2:]], capture_output=True, text=True).stdout
    return [int(l.split()[0], 16) for l in out.splitlines() if l.strip()]
for fn in (0x8009d9f0,):
    for site in xrefs(fn):
        ins = ppc.dis(d, site - 4 * 10, 11)
        r3 = [f"{a:08x} {m} {o}" for a, m, o in ins if re.match(r"r3,", o) and m in ("li", "addi", "mr", "lwz", "lhz", "addis", "ori", "add")]
        imms = [int(x, 16) for a, m, o in ins for x in re.findall(r"0x([0-9a-f]+)", o) if m in ("li", "addi")]
        hi = [hex(v) for v in imms if 0x3000 <= v < 0x3720]
        print(f"{site:08x}", "| r3:", r3[-1] if r3 else "?", "| hi-range imms:", hi)
