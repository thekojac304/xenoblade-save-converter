"""Patch the copied 2H GUI (phase3a/gui) for three platforms. Run once on a fresh copy."""
import sys

G = r"C:\Dev\XC_Wii_to_DE_Research\phase3a\gui"


def patch(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        if old not in s:
            sys.exit(f"pattern not found in {path}:\n{old[:300]}")
        s = s.replace(old, new, 1)
    open(path, "w", encoding="utf-8", newline="\n").write(s)


patch(G + r"\xcgui\__init__.py", [
    ('"""XC Save Converter: desktop front end (PySide6) for the xcconv engine (Phase 2G)."""',
     '"""XC Save Converter: desktop front end (PySide6) for the xcconv engine (Phase 2G; three platforms since 3A)."""'),
    ('APP_VERSION = "2H-rc1"', 'APP_VERSION = "3A-rc1"')])

patch(G + r"\xcgui\app.py", [
    ('''        tools = os.path.normpath(os.path.join(here, "..", "..", "tools"))
        if tools not in sys.path:
            sys.path.insert(0, tools)''',
     '''        for rel in (("..", "..", "..", "tools"), ("..", "..", "src")):      # 2H engine + Phase 3A modules
            p = os.path.normpath(os.path.join(here, *rel))
            if p not in sys.path:
                sys.path.insert(0, p)'''),
    ('''        out["dest_preview"] = win.dest_info.text()''', '''        out["dest_preview"] = win.dest_info.text()
        out["direction"] = win.direction()'''),
    ('''        if job.get("dest"):
            win.dest_pick.set_path(job["dest"])
            _wait_idle(app, win)''', '''        if job.get("target"):
            win.set_target(job["target"])
            _wait_idle(app, win)
        if job.get("dest"):
            win.dest_pick.set_path(job["dest"])
            _wait_idle(app, win)
        if job.get("keep_this_progress"):
            win.branch = True''')])

M = G + r"\xcgui\main_window.py"
BS = "\\\\"
patch(M, [
    ('"""Main window (Phase 2H): three steps and one button.',
     '"""Main window (Phase 2H; three platforms in 3A): three steps and one button.'),
    ("  1  Your save                the save to convert; its game decides the direction",
     "  1  Your save                the save to convert (Wii, Definitive Edition or New 3DS); a small \"Convert to\"\n"
     "                              choice is shown only while step 2 is empty (a destination save decides it)"),
    ("import xcservice as svc\n", "import xcservice3 as svc\n"),
    ('''GAME = {"wii": "Wii", "de": "Definitive Edition"}
TARGET = {"wii_to_de": "de", "de_to_wii": "wii"}
SAVE_FILTER = {"wii": "Wii saves (monado01 monado02 monado03);;All files (*)",
               "de": "Definitive Edition saves (bfsgame*.sav);;All files (*)",
               "any": "Xenoblade saves (monado01 monado02 monado03 bfsgame*.sav);;All files (*)"}''',
     '''GAME = {"wii": "Wii", "de": "Definitive Edition", "3ds": "New 3DS"}
TARGET = svc.TARGET
DEFAULT_TARGET = {"wii": "de", "de": "wii", "3ds": "wii"}
SAVE_FILTER = {"wii": "Wii saves (monado01 monado02 monado03);;All files (*)",
               "de": "Definitive Edition saves (bfsgame*.sav);;All files (*)",
               "3ds": "Xenoblade 3D saves (monado01 monado02 monado03);;All files (*)",
               "any": "Xenoblade saves (monado01 monado02 monado03 bfsgame*.sav);;All files (*)"}'''),
    ('''    game = "Wii" if pv["game"] == "wii" else f"Definitive Edition (v{pv['de_version']})"''',
     '''    game = {"wii": "Wii", "3ds": "New 3DS"}.get(pv["game"]) or f"Definitive Edition (v{pv['de_version']})"'''),
    ('''        self.branch = False                  # explicit "keep this save's progress" confirmation (one conversion)''',
     '''        self.branch = False                  # explicit "keep this save's progress" confirmation (one conversion)
        self.target_choice = None            # "Convert to" choice while no destination save decides the target'''),
    ('''        self.src_info = label(selectable=True)
        self.src_notice = Notice()
        for w in (self.src_pick, self.src_info, self.src_notice):
            l1.addWidget(w)''', '''        self.src_info = label(selectable=True)
        self.target_row = QWidget()
        trow = QHBoxLayout(self.target_row)
        trow.setContentsMargins(0, 0, 0, 0)
        tlab = label("Convert to:", wrap=False)
        self.target_combo = QComboBox()
        self.target_combo.setAccessibleName("Convert to")
        self.target_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.target_combo.activated.connect(lambda i: self.set_target(self.target_combo.itemData(i)))
        tlab.setBuddy(self.target_combo)
        trow.addWidget(tlab)
        trow.addWidget(self.target_combo)
        trow.addStretch(1)
        self.target_row.hide()
        self.src_notice = Notice()
        for w in (self.src_pick, self.src_info, self.target_row, self.src_notice):
            l1.addWidget(w)'''),
    ('''                                   placeholder="Drop a Wii or Definitive Edition save here, or browse")''',
     '''                                   placeholder="Drop a Wii, Definitive Edition or New 3DS save here, or browse")'''),
    ('''    def direction(self):
        if self.src and self.src.get("game") in ("wii", "de"):
            return "wii_to_de" if self.src["game"] == "wii" else "de_to_wii"
        return None''', '''    def direction(self):
        if self.src and self.src.get("game") in GAME:
            return svc.direction_for(self.src["game"], self.target_game())
        return None

    def target_game(self):
        """The destination platform: a destination save decides; otherwise the "Convert to" choice."""
        if not self.src or self.src.get("game") not in GAME:
            return None
        g = self.src["game"]
        p = self.dest_pick.path()
        if p:
            k = svc.detect(p)["kind"]
            if k in GAME and k != g:
                return k
        t = self.target_choice
        return t if t in GAME and t != g else DEFAULT_TARGET[g]

    def set_target(self, t):
        if t == self.target_choice:
            return
        self.target_choice = t
        self.log(f"convert to: {t}")
        self._gen += 1
        self.plan = self.plan_error = None
        self._dest_check()
        if self.src and not self.src.get("pending") and not self.src_problem:
            self._plan()
        self.refresh()

    def _target_items(self):
        g = self.src.get("game") if self.src else None
        show = bool(g in GAME and not self.dest_pick.path())
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        if g in GAME:
            for t in ("wii", "de", "3ds"):
                if t != g:
                    self.target_combo.addItem(GAME[t], t)
            i = self.target_combo.findData(self.target_game())
            self.target_combo.setCurrentIndex(max(i, 0))
        self.target_combo.blockSignals(False)
        self.target_row.setVisible(show)'''),
    ('''        self.chosen_record, self.start_fresh, self.branch = None, False, False
        set_text(self.src_info, "")''', '''        self.chosen_record, self.start_fresh, self.branch = None, False, False
        self.target_choice = None
        set_text(self.src_info, "")'''),
    ('''                "wii-empty": ("Empty Wii save slot", "This slot does not contain a game."),''',
     '''                "wii-empty": ("Empty Wii save slot", "This slot does not contain a game."),
                "3ds-empty": ("Empty 3DS save slot", "This slot does not contain a game."),
                "3ds-damaged": ("This 3DS save is damaged", "It is not repaired or converted. Choose another copy."),'''),
    ('''                "unknown": ("Not a Xenoblade Chronicles save", "Choose a Wii save (monado01–03) or a Definitive "
                                                               "Edition save (bfsgameNN.sav).")}''',
     '''                "unknown": ("Not a Xenoblade Chronicles save", "Choose a Wii or New 3DS save (monado01–03) or a "
                                                               "Definitive Edition save (bfsgameNN.sav).")}'''),
    ('''            comp = svc.compatibility(p) if k == "de" else svc.wii_compatibility(p)''',
     '''            comp = svc.compatibility(p) if k == "de" else svc.wii_compatibility(p)'''),
    ('''        if tgt and k != tgt:
            what = {"wii-empty": "This Wii slot is empty.", "sidecar": "This is a conversion record, not a save.",
                    "missing": "File not found."}.get(k, f"This is not a {GAME[tgt]} save.")''',
     '''        if tgt and k != tgt:
            what = {"wii-empty": "This Wii slot is empty.", "3ds-empty": "This 3DS slot is empty.",
                    "3ds-damaged": "This 3DS save is damaged.", "sidecar": "This is a conversion record, not a save.",
                    "missing": "File not found."}.get(k, f"This is not a {GAME[tgt]} save.")'''),
    ('''        if k not in ("wii", "de"):''', '''        if k not in ("wii", "de", "3ds"):'''),
    ('''        names = ([f"bfsgame{i:02d}.sav" for i in range(100)] if d == "wii_to_de" else
                 ["monado01", "monado02", "monado03"])''', '''        names = ([f"bfsgame{i:02d}.sav" for i in range(100)] if TARGET[d] == "de" else
                 ["monado01", "monado02", "monado03"])'''),
    ('''        return f"bfsgame{slot}.sav" if self.direction() == "wii_to_de" else slot''',
     '''        return f"bfsgame{slot}.sav" if TARGET.get(self.direction()) == "de" else slot'''),
    ('''        if not self.dest_pick.path() and not no_current:
            return f"Choose a {tgt} save in step 2."''', '''        optional = self.direction() == "3ds_to_wii" and not self.returning()   # lossless: no template needed
        if not self.dest_pick.path() and not no_current and not optional:
            return f"Choose a {tgt} save in step 2."'''),
    ('''    def refresh(self):
        self._step2_texts()''', '''    def refresh(self):
        self._target_items()
        self._step2_texts()'''),
    ('''        common = dict(out=out_dir, slot=self.slot(), dry_run=self.adv.opt_dry.isChecked())''',
     '''        common = dict(out=out_dir, slot=self.slot(), dry_run=self.adv.opt_dry.isChecked())
        if svc.is3(d):
            overflow = "sidecar" if self.adv.opt_overflow.isChecked() else "refuse"
            if self.returning():
                return svc.ThreeDSRequest(direction=d, source=src, record=self.plan.sidecar, current=dest,
                                          no_current=dest is None,
                                          template=dest if svc.TARGET[d] == "3ds" else None,
                                          branch="keep_source" if self.branch else None, overflow=overflow, **common)
            return svc.ThreeDSRequest(direction=d, source=src, template=dest if svc.TARGET[d] != "wii" else None,
                                      overflow=overflow, **common)'''),
    ('''        tgt = "Definitive Edition" if res.direction == "wii_to_de" else "Wii"''',
     '''        tgt = GAME[TARGET[res.direction]]'''),
    ('''        elif res.direction == "wii_to_de":
            self.res_guide.setText(''', '''        elif TARGET[res.direction] == "3ds":
            self.res_guide.setText(f"Back up your 3DS saves, then copy {fname} into the game's save folder in Azahar "
                                   "(right-click the game > Open Save Data Location). For a real New 3DS, the "
                                   "checkpoint folder is a complete backup for Checkpoint (not yet tested on "
                                   "hardware). Keep this output folder: it is needed to convert back later.")
        elif TARGET[res.direction] == "de":
            self.res_guide.setText('''),
    ('''        if "save also progressed" in msg or "No automatic merge" in msg:''',
     '''        if "save also progressed" in msg or "No automatic merge" in msg or "both games were played" in msg:'''),
])
print("patched")
