"""Phase 3C: the 3B replay test pinned generation 4 to the 3B bytes. With the E1 fix the DE-only highest-level EXP of
characters that earned EXP in the 3DS battle at their highest level now follows their EXP (as the DE game does); every
other byte is unchanged. Replace the byte-identity assertion by exactly that statement."""
import os

P = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "phase3b", "tests",
                                  "test_synchub.py"))
s = open(P, encoding="utf-8").read()
old = '        self.assertEqual(fx.out("de", 4), f("de_gen4.sav"))\n'
new = '''        # 3B: byte-identical to de_gen4.sav. Phase 3C (E1): the highest-level EXP word (+0xF0) of characters that
        # earned EXP at their highest level in the 3DS battle now equals their EXP, as the DE game keeps it; nothing else
        new4, old4 = fx.out("de", 4), f("de_gen4.sav")
        ch = 0x152728
        diff = [i for i in range(len(new4)) if new4[i] != old4[i]]
        self.assertTrue(all(ch <= i < ch + 0x138 * 16 and 0xF0 <= (i - ch) % 0x138 < 0xF4 for i in diff), diff[:8])
        for k in range(1, 8):
            o = ch + 0x138 * (k - 1)
            if new4[o + 0xF0:o + 0xF4] != old4[o + 0xF0:o + 0xF4]:
                self.assertEqual(new4[o + 0xF0:o + 0xF4], new4[o + 4:o + 8])          # = current EXP
                self.assertEqual(new4[o:o + 4], new4[o + 0xEC:o + 0xF0])              # at the highest level
        self.assertEqual(sh("de", new4), sh("de", old4))
'''
assert old in s
s = s.replace(old, new)
open(P, "w", encoding="utf-8").write(s)
print("patched")
