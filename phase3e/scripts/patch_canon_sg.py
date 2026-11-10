"""Phase 3E: canonical stored gear (shared["stored_gear"], only when the save has stored characters)."""
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
p = os.path.join(ROOT, "tools", "canon.py")
s = open(p, encoding="utf-8").read()
A = '''                           if fm.wii_get(wii, 0x220 + q) not in (254, 255) and any(qc.wii_to_de(wii, q))},
    }
    wii_only = {'''
B = '''                           if fm.wii_get(wii, 0x220 + q) not in (254, 255) and any(qc.wii_to_de(wii, q))},
    }
    _stored_gear(shared, "wii", wii, T, ir)
    wii_only = {'''
C = '''                           if fm.de_get(de, 0x220 + q) not in (254, 255) and any(de[qc.DE_QC + 8 * q:qc.DE_QC + 8 * q + 8])},
    }
    de_flags = '''
D = '''                           if fm.de_get(de, 0x220 + q) not in (254, 255) and any(de[qc.DE_QC + 8 * q:qc.DE_QC + 8 * q + 8])},
    }
    _stored_gear(shared, "de", de, T)
    de_flags = '''
E = '''# ------------------------------------------------------------------------------------------------- utilities
def jsonable(c):'''
F = '''def _stored_gear(shared, game, raw, T, ir=None):
    """Phase 3E: equipment stored for party members who are away (tools/stored_gear). Present only when the save has
    such characters, so every other save's canonical state is unchanged."""
    import stored_gear
    sg, bad = stored_gear.read_all(game, raw, shared["story"], shared["party"], T, ir=ir)
    if sg or bad:
        shared["stored_gear"] = {**sg, **{k: {"unreadable": v} for k, v in bad.items()}}


# ------------------------------------------------------------------------------------------------- utilities
def jsonable(c):'''
for a, b in ((A, B), (C, D), (E, F)):
    assert a in s, a[:60]
    s = s.replace(a, b, 1)
open(p, "w", encoding="utf-8").write(s)
print("ok")
