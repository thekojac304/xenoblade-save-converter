import sys, re
sys.path.insert(0, r"C:\Dev\XC_Wii_to_DE_Research\phase3a\src")
import arm, capstone
d = arm.data()
cs = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
# disassemble whole text once, cache
import pickle, os
cache = r"C:\Dev\XC_Wii_to_DE_Research\phase3a\research\rom\text_dis.pkl"
if os.path.exists(cache):
    ins = pickle.load(open(cache, "rb"))
else:
    ins = []
    for off in range(0, 0x479000 - 0x100000, 4):
        r = list(cs.disasm(d[off:off+4], 0x100000 + off))
        ins.append((0x100000 + off, r[0].mnemonic, r[0].op_str) if r else (0x100000 + off, ".word", ""))
    pickle.dump(ins, open(cache, "wb"))
pats = [re.compile(p) for p in sys.argv[1:]]
# find windows where all patterns occur within 6 instructions in order
for i in range(len(ins)):
    if not pats[0].search(ins[i][1] + " " + ins[i][2]): continue
    j = i; ok = True; seq=[i]
    for p in pats[1:]:
        k = j + 1
        while k < min(j + 6, len(ins)) and not p.search(ins[k][1] + " " + ins[k][2]): k += 1
        if k >= min(j + 6, len(ins)): ok = False; break
        j = k; seq.append(k)
    if ok:
        print(" ; ".join(f"{ins[x][0]:x} {ins[x][1]} {ins[x][2]}" for x in range(seq[0]-2, seq[-1]+1)))
