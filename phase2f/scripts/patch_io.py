"""Phase 2F: close table files and read JSON specs as UTF-8 (portability; no behaviour change)."""
import os

T = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools")


def rep(name, a, b):
    p = os.path.join(T, name)
    s = open(p, encoding="utf-8").read()
    assert s.count(a) == 1, (name, a[:60], s.count(a))
    s = s.replace(a, b)
    open(p, "w", encoding="utf-8").write(s)


rep("phase2c.py", 'w = json.load(open(paths.data("bdat_wii.json"), encoding="utf-8"))',
    'w = _load_json(paths.data("bdat_wii.json"))')
rep("phase2c.py", 'd = json.load(open(paths.data("bdat_de.json"), encoding="utf-8"))',
    'd = _load_json(paths.data("bdat_de.json"))')
rep("phase2c.py", "\ndef tables(", '''
def _load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def tables(''')
rep("convert.py", 'T["de"] = json.load(open(paths.data("bdat_de.json"), encoding="utf-8"))',
    'with open(paths.data("bdat_de.json"), encoding="utf-8") as f:\n        T["de"] = json.load(f)')
rep("quest_counters.py", 'B = json.load(open(paths.data("bdat_wii.json"), encoding="utf-8"))',
    'with open(paths.data("bdat_wii.json"), encoding="utf-8") as f:\n            B = json.load(f)')
rep("achievements.py", 'json.load(open(os.path.join(ROOT, "specs", "wii_award_tiers.json"))).items()}',
    '_spec("wii_award_tiers.json").items()}')
rep("achievements.py", "\ndef rules(", '''
def _spec(name):
    with open(os.path.join(ROOT, "specs", name), encoding="utf-8") as f:
        return json.load(f)


def rules(''')
print("ok")
