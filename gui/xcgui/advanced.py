"""The Advanced window: options that are rarely needed, game-data setup, inspection tools, log and diagnostics.
Nothing here is required for a normal conversion."""
import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget)

import dump_bdat
import paths
import safeio
import xcservice as svc

from .messages import explain
from .widgets import Notice, PathPicker, label, soft

SAVE_FILTER = "Xenoblade saves (monado01 monado02 monado03 bfsgame*.sav);;All files (*)"
RECORD_FILTER = "Conversion records (*.sidecar.json);;All files (*)"


def default_data_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    return os.path.join(base, "XCSaveConverter", "game_data")


def text_out(name):
    t = QPlainTextEdit()
    t.setReadOnly(True)
    t.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    t.setAccessibleName(name)
    t.setMinimumHeight(120)
    return t


class AdvancedDialog(QDialog):
    TABS = ("options", "data", "tools", "log", "diagnostics")

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Advanced")
        self.setMinimumSize(520, 420)
        self.resize(760, 560)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._options(), "&Options")
        self.tabs.addTab(self._data(), "&Game data")
        self.tabs.addTab(self._tools(), "&Tools")
        self.log_view = text_out("Log")
        self.tabs.addTab(self.log_view, "&Log")
        self.tabs.addTab(self._diag(), "&Diagnostics")
        self.tabs.currentChanged.connect(lambda i: self.fill_diag() if i == 4 else None)
        lay.addWidget(self.tabs)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.hide)
        lay.addWidget(bb)

    def show_tab(self, name):
        self.tabs.setCurrentIndex(self.TABS.index(name))
        self.show()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------------------------------- options
    def _options(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        g = QGroupBox("Conversion")
        gl = QVBoxLayout(g)
        self.opt_dry = QCheckBox("C&heck only: convert and verify, but write nothing")
        self.opt_overflow = QCheckBox("&Keep extra items for later when the Wii inventory is full (DE → Wii)")
        self.opt_same = QCheckBox("The Wii save in step 2 is an earlier save of this &same playthrough (DE → Wii)")
        self.opt_no_current = QCheckBox("I no longer have a save of the destination game (return conversions only)")
        for c in (self.opt_dry, self.opt_overflow, self.opt_same, self.opt_no_current):
            gl.addWidget(c)
            c.toggled.connect(lambda _: self.win.inputs_changed())
        lay.addWidget(g)
        g = QGroupBox("Conversion record")
        gl = QVBoxLayout(g)
        gl.addWidget(label("Every conversion stores a record (a .sidecar.json file) in its output folder. It keeps "
                           "what only one game version can hold and is found automatically when you convert back."))
        self.record_status = label("Found automatically when you convert a save back.", selectable=True)
        gl.addWidget(self.record_status)
        row = QHBoxLayout()
        b = QPushButton("&Choose a record file…")
        b.clicked.connect(self.win.choose_record_file)
        c = QPushButton("&Find automatically")
        c.clicked.connect(self.win.clear_record_choice)
        row.addWidget(b)
        row.addWidget(c)
        row.addStretch(1)
        gl.addLayout(row)
        lay.addWidget(g)
        lay.addStretch(1)
        return w

    def set_record_status(self, text):
        self.record_status.setText(text)

    # ------------------------------------------------------------------------------------------- game data
    def _data(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(label("The converter needs two tables made from your own copies of both games: bdat_wii.json "
                            "and bdat_de.json. They are not included and must not be shared."))
        self.data_status = Notice()
        lay.addWidget(self.data_status)
        g = QGroupBox("Use tables you already have")
        gl = QFormLayout(g)
        self.data_pick = PathPicker("Choose the folder with bdat_wii.json and bdat_de.json", "folder",
                                    name="Game data folder")
        gl.addRow("Folder:", self.data_pick)
        b = QPushButton("&Use this folder")
        b.clicked.connect(lambda: self.win.set_data_dir(self.data_pick.path()))
        gl.addRow("", b)
        lay.addWidget(g)
        g = QGroupBox("Create them from your game files")
        gl = QFormLayout(g)
        gl.addRow(label("Wii: the extracted disc's files folder (with lang\\en\\static.arc). Definitive Edition: the "
                        "extracted romfs folder (with bdat\\*.bdat). Game files are only read."))
        self.mk_wii = PathPicker("Choose the extracted Wii 'files' folder", "folder", name="Wii game files folder")
        self.mk_de = PathPicker("Choose the extracted DE romfs folder", "folder", name="DE romfs folder")
        self.mk_out = PathPicker("Choose where to store the tables", "folder", name="Tables destination")
        self.mk_out.set_path(default_data_dir(), emit=False)
        gl.addRow("Wii files:", self.mk_wii)
        gl.addRow("DE romfs:", self.mk_de)
        gl.addRow("Store in:", self.mk_out)
        self.mk_btn = QPushButton("C&reate tables")
        self.mk_btn.clicked.connect(self.create_tables)
        gl.addRow("", self.mk_btn)
        self.mk_status = Notice()
        gl.addRow(self.mk_status)
        lay.addWidget(g)
        lay.addStretch(1)
        return w

    def data_refresh(self):
        if svc.tables_available():
            d = paths.data_dir()
            self.data_status.show_message("ok", "Game data is set up", soft(d))
            self.data_pick.set_path(d, emit=False)
        else:
            self.data_status.show_message("warn", "Game data is not set up yet",
                                          "Choose a folder with your tables, or create them.")

    def create_tables(self):
        wii, rom, out = self.mk_wii.path(), self.mk_de.path(), self.mk_out.path()
        miss = dump_bdat.missing_inputs(wii, rom)
        if not out:
            miss.append("Choose where to store the tables.")
        if miss:
            self.mk_status.show_message("error", "Some game files were not found", "\n".join(miss))
            return
        try:
            safeio.guard_out(os.path.join(out, "bdat_wii.json"))
        except safeio.Refused as e:
            f = explain(e)
            self.mk_status.show_message("error", f.title, f.text, f.detail)
            return
        self.mk_btn.setEnabled(False)
        self.mk_status.show_message("info", "Creating tables…", "This takes a minute.")

        def done(counts):
            self.mk_btn.setEnabled(True)
            self.mk_status.show_message("ok", "Tables created", f"{counts.get('wii', 0)} Wii and "
                                        f"{counts.get('de', 0)} Definitive Edition tables in {soft(out)}")
            self.win.set_data_dir(out)

        def failed(e, tb):
            self.mk_btn.setEnabled(True)
            self.mk_status.show_message("error", "The tables could not be created",
                                        "Check that both folders are the extracted game files.",
                                        f"{type(e).__name__}: {e}")

        self.win.engine.submit(lambda: dump_bdat.main(wii, rom, out=out, log=lambda *_: None),
                               on_done=done, on_failed=failed)

    # ------------------------------------------------------------------------------------------- tools
    def _tools(self):
        tabs = QTabWidget()
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(label("Everything the converter reads from a save, and its structural checks."))
        self.ins_pick = PathPicker("Choose a save", "file", SAVE_FILTER, name="Save to inspect")
        l.addWidget(self.ins_pick)
        r = QHBoxLayout()
        b1 = QPushButton("&Inspect")
        b1.clicked.connect(lambda: self.run("inspect"))
        b2 = QPushButton("&Validate")
        b2.clicked.connect(lambda: self.run("validate"))
        r.addWidget(b1)
        r.addWidget(b2)
        r.addStretch(1)
        l.addLayout(r)
        self.ins_out = text_out("Inspector output")
        l.addWidget(self.ins_out, 1)
        tabs.addTab(w, "Save inspector")

        w = QWidget()
        l = QFormLayout(w)
        l.addRow(label("Converts in memory to the other game and back and lists differences. Writes nothing."))
        self.rt_src = PathPicker("Choose a save", "file", SAVE_FILTER, name="Round-trip save")
        self.rt_other = PathPicker("Choose a save of the other game", "file", SAVE_FILTER,
                                   name="Round-trip save of the other game")
        l.addRow("Save:", self.rt_src)
        l.addRow("Other game's save:", self.rt_other)
        b = QPushButton("&Run round-trip check")
        b.clicked.connect(lambda: self.run("roundtrip"))
        l.addRow("", b)
        self.rt_out = text_out("Round-trip output")
        l.addRow(self.rt_out)
        tabs.addTab(w, "Round-trip check")

        w = QWidget()
        l = QVBoxLayout(w)
        self.sc_info_pick = PathPicker("Choose a conversion record", "file", RECORD_FILTER,
                                       name="Conversion record to show")
        l.addWidget(self.sc_info_pick)
        b = QPushButton("S&how record")
        b.clicked.connect(lambda: self.run("sidecar"))
        l.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        self.sc_info_out = text_out("Conversion record details")
        l.addWidget(self.sc_info_out, 1)
        tabs.addTab(w, "Conversion record")

        w = QWidget()
        l = QFormLayout(w)
        l.addRow(label("Can a Definitive Edition save become a Wii save, and does its inventory fit a Wii save?"))
        self.cc_de = PathPicker("Choose a Definitive Edition save", "file", SAVE_FILTER, name="DE save to check")
        self.cc_base = PathPicker("Choose a Wii save (optional)", "file", SAVE_FILTER, name="Wii save (optional)")
        l.addRow("DE save:", self.cc_de)
        l.addRow("Wii save (optional):", self.cc_base)
        b = QPushButton("Check co&mpatibility")
        b.clicked.connect(lambda: self.run("compat"))
        l.addRow("", b)
        self.cc_out = text_out("Compatibility output")
        l.addRow(self.cc_out)
        tabs.addTab(w, "Compatibility")
        self.tool_tabs = tabs
        return tabs

    def run(self, what):
        out = {"inspect": self.ins_out, "validate": self.ins_out, "roundtrip": self.rt_out,
               "sidecar": self.sc_info_out, "compat": self.cc_out}[what]
        if not svc.tables_available() and what != "sidecar":
            out.setPlainText("Set up the game data first (Game data tab).")
            return
        if what in ("inspect", "validate"):
            p = self.ins_pick.path()
            fn = (lambda: svc.summary(load_any(p))) if what == "inspect" else (lambda: svc.validate_file(p))
        elif what == "roundtrip":
            s, o = self.rt_src.path(), self.rt_other.path()
            k = svc.detect(s)["kind"]
            fn = (lambda: svc.roundtrip(wii=s, template=o)) if k == "wii" else (lambda: svc.roundtrip(de=s, base=o))
        elif what == "sidecar":
            p = self.sc_info_pick.path()
            fn = lambda: svc.sidecar_info(p)  # noqa: E731
        else:
            de, base = self.cc_de.path(), self.cc_base.path() or None
            fn = lambda: svc.compatibility(de, base)  # noqa: E731
        out.setPlainText("Working…")

        def ok(r):
            out.setPlainText(json.dumps(r, indent=1, default=str))
            self.win.log(f"advanced {what}: done")

        def bad(e, tb):
            f = explain(e)
            self.win.last_error = (f, tb)
            out.setPlainText(f"{f.title}\n\n{f.text}\n\nDetails: {f.detail}")
            self.win.log(f"advanced {what}: {f.detail}")

        self.win.engine.submit(fn, on_done=ok, on_failed=bad)

    # ------------------------------------------------------------------------------------------- diagnostics
    def _diag(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(label("Program versions, settings, selected files (paths and checksums, no save contents) and "
                          "the last result or error. Copy it when you report a problem."))
        r = QHBoxLayout()
        b = QPushButton("R&efresh")
        b.clicked.connect(self.fill_diag)
        c = QPushButton("Cop&y to clipboard")
        c.clicked.connect(self.win.copy_diagnostics)
        r.addWidget(b)
        r.addWidget(c)
        r.addStretch(1)
        l.addLayout(r)
        self.diag_out = text_out("Diagnostic report")
        l.addWidget(self.diag_out, 1)
        return w

    def fill_diag(self):
        self.diag_out.setPlainText(self.win.diagnostics())


def load_any(p):
    k = svc.detect(p)["kind"]
    if k == "wii":
        return svc.load_wii(p, "save")
    if k == "de":
        return svc.load_de(p, "save")
    return safeio.read_input(p, "save")
