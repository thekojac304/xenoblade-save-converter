"""Main window (Phase 2H; three platforms in 3A): three steps and one button.

  1  Your save                the save to convert (Wii, Definitive Edition or New 3DS); a small "Convert to"
                              choice is shown only while step 2 is empty (a destination save decides it)
  2  Destination save         a save of the other game: the starting template of a first conversion, or the current
                              save of that game when a conversion is brought back (used for the safety checks)
  3  Save converted file to   a normal folder; a new sub-folder is created for every conversion
  [ Convert Save ]            Original saves are never modified.

The window decides nothing about save data itself: format detection, preview, conversion history
(xcservice.resolve_history), slot suggestion, conversion, verification and writing are xcservice calls (the same code
the CLI runs), executed on the worker thread. History questions are asked only when the service cannot decide safely.
"""
import datetime
import json
import os
import platform
import sys

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import QSettings, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QInputDialog, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
                               QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

import paths
import safeio
import sidecar as scmod
import xcservice3 as svc

from . import APP_NAME, APP_VERSION
from .advanced import RECORD_FILTER, AdvancedDialog, default_data_dir
from .messages import explain, explain_problem
from .widgets import DropArea, Notice, PathPicker, PrimaryButton, label, set_text

GAME = {"wii": "Wii", "de": "Definitive Edition", "3ds": "New 3DS"}
TARGET = svc.TARGET
DEFAULT_TARGET = {"wii": "de", "de": "wii", "3ds": "wii"}
SAVE_FILTER = {"wii": "Wii saves (monado01 monado02 monado03);;All files (*)",
               "de": "Definitive Edition saves (bfsgame*.sav);;All files (*)",
               "3ds": "Xenoblade 3D saves (monado01 monado02 monado03);;All files (*)",
               "any": "Xenoblade saves (monado01 monado02 monado03 bfsgame*.sav);;All files (*)"}
CONTENT_WIDTH = 680


def default_output_parent():
    return os.path.join(os.path.expanduser("~"), "Documents", "XC Save Converter", "Converted saves")


def fmt_name(f):
    if f == "sx4e":
        return "Wii"
    if f.startswith("de-v"):
        return "Definitive Edition"
    return f


def when(path):
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%d %b %Y, %H:%M")
    except OSError:
        return "an earlier date"


def short_preview(pv):
    """'Wii · Eryth Sea · 22:01:57 · Shulk Lv 52' (fields the decoders do not establish say Unknown)."""
    lead = pv["party"][0] if pv.get("party") else None
    lv = f"{lead['name']} Lv {lead['level']}" if lead and lead.get("level") is not None else "level Unknown"
    area = pv.get("map_name") or "Unknown area"
    game = {"wii": "Wii", "3ds": "New 3DS"}.get(pv["game"]) or f"Definitive Edition (v{pv['de_version']})"
    return f"{game}  ·  {area}  ·  {pv['play_time']}  ·  {lv}"


class ChooseRecordDialog(QDialog):
    """Asked only when several earlier conversions match, or only an older one does."""

    def __init__(self, parent, choices, intro):
        super().__init__(parent)
        self.setWindowTitle("Choose the earlier conversion")
        self.path = None
        lay = QVBoxLayout(self)
        lay.addWidget(label(intro))
        self.list = QListWidget()
        self.list.setAccessibleName("Earlier conversions")
        for c in sorted(choices, key=lambda c: (-c.generation, c.path)):
            how = "matches exactly" if c.status == "exact" else "you played after it"
            age = "" if c.newest else "  ·  older"
            it = QListWidgetItem(f"{when(c.path)}  ·  {os.path.basename(os.path.dirname(c.path))}  ·  {how}{age}")
            it.setData(Qt.ItemDataRole.UserRole, c.path)
            it.setToolTip(c.path)
            self.list.addItem(it)
        self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())
        lay.addWidget(self.list)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Use this conversion")
        browse = bb.addButton("Other file…", QDialogButtonBox.ButtonRole.ActionRole)
        browse.clicked.connect(self._browse)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.resize(560, 300)

    def _browse(self):
        p, _ = QFileDialog.getOpenFileName(self, "Choose a conversion record", "", RECORD_FILTER)
        if p:
            self.path = p
            super().accept()

    def accept(self):
        it = self.list.currentItem()
        if it:
            self.path = it.data(Qt.ItemDataRole.UserRole)
        super().accept()


class MainWindow(QMainWindow):
    conversion_finished = Signal(bool)   # True = success (automation and tests)
    plan_ready = Signal()                # a conversion-history decision is available

    def __init__(self, settings=None, engine=None):
        super().__init__()
        from .worker import Engine
        self.settings = settings or QSettings("XCSaveConverter", "XC Save Converter")
        self.engine = engine or Engine(self)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(480, 420)
        self.src = self.dest = None          # preview dicts
        self.src_problem = self.dest_problem = None
        self.compat_problems = []
        self.plan = None                     # svc.HistoryPlan
        self.plan_error = None
        self.plan_pending = False
        self.capacity_over = []
        self.chosen_record = None            # conversion record chosen by the user
        self.start_fresh = False             # explicit "start fresh" confirmation
        self.branch = False                  # explicit "keep this save's progress" confirmation (one conversion)
        self.target_choice = None            # "Convert to" choice while no destination save decides the target
        self.slot_hint = None
        self.running = False
        self.last_result = None
        self.last_error = None
        self._gen = 0              # destination / history results; older ones are dropped
        self._src_gen = 0          # source preview results
        self._log_lines = []
        self.adv = AdvancedDialog(self)
        self._build()
        self._apply_settings()
        self._dest_check()
        set_text(self.src_info, "")
        self.refresh()

    # ------------------------------------------------------------------------------------------- layout
    def _build(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.stack.addWidget(self._scroll(self._form_page()))
        self.stack.addWidget(self._scroll(self._result_page()))
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.src_pick._browse)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._convert_shortcut)

    @staticmethod
    def _scroll(inner):
        holder = QWidget()
        h = QHBoxLayout(holder)
        h.setContentsMargins(20, 16, 20, 16)
        h.addStretch(1)
        inner.setMaximumWidth(CONTENT_WIDTH)
        h.addWidget(inner, 100)
        h.addStretch(1)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QScrollArea.Shape.NoFrame)
        sa.setWidget(holder)
        return sa

    def _step(self, lay, number, title, mnemonic_title):
        head = QHBoxLayout()
        num = label(number, bold=True, scale=1.15, wrap=False)
        num.setFixedWidth(22)
        t = label(mnemonic_title, bold=True, scale=1.15, wrap=False)
        head.addWidget(num)
        head.addWidget(t, 1)
        lay.addLayout(head)
        return t

    def _form_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.setup_notice = Notice()
        lay.addWidget(self.setup_notice)

        # 1
        self.drop1 = DropArea()
        l1 = QVBoxLayout(self.drop1)
        l1.setContentsMargins(6, 6, 6, 6)
        t = self._step(l1, "1", "Your save", "Your &save")
        self.src_pick = PathPicker("Choose your save", "file", SAVE_FILTER["any"], name="Your save",
                                   placeholder="Drop a Wii, Definitive Edition or New 3DS save here, or browse")
        t.setBuddy(self.src_pick.edit)
        self.src_pick.changed.connect(self.set_source)
        self.drop1.dropped.connect(self.src_pick.set_path)
        self.src_info = label(selectable=True)
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
            l1.addWidget(w)
        lay.addWidget(self.drop1)

        # 2
        self.drop2 = DropArea()
        l2 = QVBoxLayout(self.drop2)
        l2.setContentsMargins(6, 6, 6, 6)
        self.dest_title = self._step(l2, "2", "Destination save", "&Destination save")
        self.dest_pick = PathPicker("Choose a save of the destination game", "file", SAVE_FILTER["any"],
                                    name="Destination save")
        self.dest_title.setBuddy(self.dest_pick.edit)
        self.dest_pick.changed.connect(self.set_dest)
        self.drop2.dropped.connect(self.dest_pick.set_path)
        self.dest_hint = label()
        self.dest_info = label(selectable=True)
        self.dest_notice = Notice()
        for w in (self.dest_pick, self.dest_hint, self.dest_info, self.dest_notice):
            l2.addWidget(w)
        lay.addWidget(self.drop2)

        # 3
        box3 = QWidget()
        l3 = QVBoxLayout(box3)
        l3.setContentsMargins(6, 6, 6, 6)
        t = self._step(l3, "3", "Save converted file to", "Save converted file &to")
        self.out_pick = PathPicker("Choose where converted saves are created", "folder", name="Output folder")
        t.setBuddy(self.out_pick.edit)
        self.out_pick.changed.connect(lambda _: self.refresh())
        self.slot_row = QWidget()
        row = QHBoxLayout(self.slot_row)
        row.setContentsMargins(0, 0, 0, 0)
        flab = label("File name:", wrap=False)
        flab.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.slot_combo = QComboBox()
        self.slot_combo.setAccessibleName("File name")
        self.slot_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.slot_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)   # 3A: no stretch when alone
        self.slot_combo.currentIndexChanged.connect(lambda _: self.refresh())
        flab.setBuddy(self.slot_combo)
        self.slot_note = label()
        row.addWidget(flab)
        row.addWidget(self.slot_combo)
        row.addWidget(self.slot_note, 1)
        row.addStretch(0)            # 3A: keeps the row left-aligned while the note is hidden
        self.out_notice = Notice()
        l3.addWidget(self.out_pick)
        l3.addWidget(self.slot_row)
        l3.addWidget(self.out_notice)
        lay.addWidget(box3)

        # convert
        lay.addSpacing(8)
        self.convert_btn = PrimaryButton("&Convert Save")
        self.convert_btn.setDefault(True)
        self.convert_btn.clicked.connect(self.start_conversion)
        act = QVBoxLayout()
        act.setContentsMargins(6, 0, 6, 0)            # line up with the fields of the steps above
        act.setSpacing(4)
        lay.addLayout(act)
        act.addWidget(self.convert_btn)
        self.next_label = label()
        self.next_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.reassure = label("Original saves are never modified.", scale=0.92)
        self.reassure.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        act.addWidget(self.next_label)
        act.addWidget(self.reassure)
        self.fail_notice = Notice()
        act.addWidget(self.fail_notice)
        lay.addStretch(1)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 6, 0)
        self.adv_btn = QPushButton("&Advanced…")
        self.adv_btn.setFlat(True)
        self.adv_btn.clicked.connect(lambda: self.adv.show_tab("options"))
        bottom.addWidget(self.adv_btn)
        bottom.addStretch(1)
        lay.addLayout(bottom)
        return page

    def _result_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.res_title = label("Conversion complete", bold=True, scale=1.4)
        lay.addWidget(self.res_title)
        form = QFormLayout()
        self.res_game = label(selectable=True)
        self.res_file = label(selectable=True)
        self.res_folder = QLineEdit()
        self.res_folder.setReadOnly(True)
        self.res_folder.setAccessibleName("Output folder")
        form.addRow("Game:", self.res_game)
        form.addRow("New save:", self.res_file)
        form.addRow("Folder:", self.res_folder)
        lay.addLayout(form)
        self.res_warn = Notice()
        lay.addWidget(self.res_warn)
        self.res_guide = label(selectable=True)
        lay.addWidget(self.res_guide)
        row = QHBoxLayout()
        self.open_btn = PrimaryButton("&Open Output Folder")
        self.open_btn.clicked.connect(self.open_output)
        self.again_btn = QPushButton("Convert &another save")
        self.again_btn.setFlat(True)
        self.again_btn.clicked.connect(self.back_to_form)
        row.addWidget(self.open_btn)
        row.addStretch(1)
        row.addWidget(self.again_btn)
        lay.addLayout(row)
        lay.addStretch(1)
        return page

    # ------------------------------------------------------------------------------------------- settings, data
    def _apply_settings(self):
        d = self.settings.value("data_dir", "") or ""
        if not paths.has_tables(d) and paths.has_tables(default_data_dir()):
            d = default_data_dir()
        if paths.has_tables(d):
            paths.set_data_dir(d)
            svc.reset_tables()
        self.out_pick.set_path(self.settings.value("output_parent", "") or default_output_parent(), emit=False)
        self._data_refresh()

    def _data_refresh(self):
        self.adv.data_refresh()
        if svc.tables_available():
            self.setup_notice.clear()
            return True
        self.setup_notice.show_message("warn", "One-time setup needed",
                                       "The converter needs data tables made from your own copies of the games.",
                                       actions=[("Set up game data…", lambda: self.adv.show_tab("data"))])
        return False

    def set_data_dir(self, d):
        if not paths.has_tables(d):
            self.adv.data_status.show_message("error", "Tables not found in this folder",
                                              "It must contain bdat_wii.json and bdat_de.json.")
            return False
        paths.set_data_dir(d)
        svc.reset_tables()
        self.settings.setValue("data_dir", os.path.normpath(d))
        self.log(f"game data folder: {d}")
        self._data_refresh()
        if self.src_pick.path():
            self.set_source(self.src_pick.path())
        return True

    def log(self, msg):
        line = f"{datetime.datetime.now():%H:%M:%S}  {msg}"
        self._log_lines.append(line)
        self.adv.log_view.appendPlainText(line)

    # ------------------------------------------------------------------------------------------- helpers
    def direction(self):
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

    def _compat_now(self):
        """Source pre-check problems that apply to the current target (the Wii -> DE party rule is DE-only;
        Wii <-> 3DS carries every character)."""
        src = self.src.get("game") if self.src else None
        if src == "de" or self.target_game() == "de":
            return list(getattr(self, "compat_all", []))
        return []

    def set_target(self, t):
        if t == self.target_choice:
            return
        self.target_choice = t
        self.compat_problems = self._compat_now()
        if not self.compat_problems and self.src_problem is None:
            self.src_notice.clear()
        self.log(f"convert to: {t}")
        self._gen += 1
        self.plan = self.plan_error = None
        self._dest_check()
        if self.src and not self.src.get("pending") and not self.src_problem:
            self._plan()
        self.refresh()

    def _src_text(self):
        if self.src and not self.src.get("pending") and self.target():
            set_text(self.src_info, f"{short_preview(self.src)}   →   {GAME[self.target()]}")

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
        self.target_row.setVisible(show)

    def target(self):
        d = self.direction()
        return TARGET[d] if d else None

    def history_folders(self):
        out = [self.out_pick.path() or default_output_parent()]
        extra = self.settings.value("history_folders", []) or []
        extra = extra if isinstance(extra, list) else [extra]
        return [f for f in dict.fromkeys(out + extra) if f]

    def _remember_folder(self, parent):
        extra = self.settings.value("history_folders", []) or []
        extra = extra if isinstance(extra, list) else [extra]
        self.settings.setValue("history_folders", list(dict.fromkeys([parent] + extra))[:10])

    def returning(self):
        return bool(self.plan and self.plan.mode == "return")

    # ------------------------------------------------------------------------------------------- step 1
    def set_source(self, p):
        self._gen += 1
        self._src_gen += 1
        gen = self._src_gen
        self.src, self.src_problem, self.compat_problems = None, None, []
        self.plan = self.plan_error = None
        self.chosen_record, self.start_fresh, self.branch = None, False, False
        self.target_choice = None
        set_text(self.src_info, "")
        self.src_notice.clear()
        self.fail_notice.clear()
        if not p:
            self._dest_check()
            self.refresh()
            return
        info = svc.detect(p)
        k = info["kind"]
        if k == "folder":
            saves = info["saves"]
            if not saves:
                return self._src_fail("No save in this folder", "Choose the save file itself (monado01–03 or "
                                                                "bfsgameNN.sav).")
            choice = saves[0]
            if len(saves) > 1:
                choice, ok = QInputDialog.getItem(self, "Choose a save", "This folder has several saves:", saves, 0,
                                                  False)
                if not ok:
                    self.src_pick.set_path("", emit=False)
                    return self.refresh()
            self.src_pick.set_path(choice)
            return
        msgs = {"missing": ("File not found", "Choose the save again."),
                "sidecar": ("This is a conversion record, not a save", "Choose the save itself."),
                "wii-empty": ("Empty Wii save slot", "This slot does not contain a game."),
                "3ds-empty": ("Empty 3DS save slot", "This slot does not contain a game."),
                "3ds-damaged": ("This 3DS save is damaged", "It is not repaired or converted. Choose another copy."),
                "unknown": ("Not a Xenoblade Chronicles save", "Choose a Wii or New 3DS save (monado01–03) or a "
                                                               "Definitive Edition save (bfsgameNN.sav).")}
        if k in msgs:
            return self._src_fail(*msgs[k])
        self.src = {"game": k, "path": os.path.abspath(p), "pending": True}
        self.log(f"source: {p} ({k})")
        self._dest_check()
        if not svc.tables_available():
            set_text(self.src_info, f"{GAME[k]} save")
            self.refresh()
            return

        def work():
            pv = svc.preview(p)
            comp = svc.compatibility(p) if k == "de" else svc.wii_compatibility(p)
            return pv, comp

        self.engine.submit(work, on_done=lambda r: self._source_ready(gen, r),
                           on_failed=lambda e, tb: self._source_failed(gen, e, tb))
        self.refresh()

    def _src_fail(self, title, text, detail=""):
        self.src_problem = title
        self.src_notice.show_message("error", title, text, detail)
        self._dest_check()
        self.refresh()

    def _source_ready(self, gen, r):
        if gen != self._src_gen:
            return
        pv, comp = r
        self.src = pv
        self._src_text()
        self.compat_all = list(dict.fromkeys(comp.get("problems", [])))
        self.compat_problems = self._compat_now()
        if self.compat_problems:
            self.src_notice.show_message("error", f"This save can't be converted to the {GAME[self.target()]} yet",
                                         "\n".join(explain_problem(x) for x in self.compat_problems),
                                         "\n".join(self.compat_problems))
        self.log(f"preview: {short_preview(pv)}")
        self._dest_check()
        self._plan()

    def _source_failed(self, gen, e, tb):
        if gen != self._src_gen:
            return
        f = explain(e)
        self.last_error = (f, tb)
        self.log(f"source refused: {f.detail}")
        self._src_fail(f.title, f.text, f.detail)

    # ------------------------------------------------------------------------------------------- step 2
    def set_dest(self, p):
        self._gen += 1
        if self.src and not self.src.get("pending"):
            self.compat_problems = self._compat_now() if hasattr(self, "compat_all") else self.compat_problems
        self.dest, self.dest_problem = None, None
        self.start_fresh, self.branch = False, False      # decisions were about the previous destination save
        self.capacity_over = []
        self.fail_notice.clear()
        self._dest_check()
        if self.src and not self.src.get("pending") and not self.src_problem:
            self._plan()
        self.refresh()

    def _dest_check(self):
        """Validate the destination save against the source's game (cheap; runs on the GUI thread)."""
        p = self.dest_pick.path()
        self.dest, self.dest_problem = None, None
        set_text(self.dest_info, "")
        self.dest_notice.clear()
        tgt = self.target()
        if tgt:
            self.dest_pick.edit.setPlaceholderText(f"Choose a {GAME[tgt]} save")
            self.dest_pick.filter = SAVE_FILTER[tgt]
        else:
            self.dest_pick.edit.setPlaceholderText("Choose your save in step 1 first")
        self._slot_items()
        if not p:
            return
        info = svc.detect(p)
        k = info["kind"]
        same = self.src_pick.path() and os.path.normcase(os.path.abspath(p)) == \
            os.path.normcase(os.path.abspath(self.src_pick.path()))
        if same:
            self.dest_problem = "same file"
            self.dest_notice.show_message("error", "This is the save from step 1", "Choose a save of the other game.")
            return
        if tgt and k != tgt:
            what = {"wii-empty": "This Wii slot is empty.", "3ds-empty": "This 3DS slot is empty.",
                    "3ds-damaged": "This 3DS save is damaged.", "sidecar": "This is a conversion record, not a save.",
                    "missing": "File not found."}.get(k, f"This is not a {GAME[tgt]} save.")
            self.dest_problem = what
            self.dest_notice.show_message("error", what, f"Choose a {GAME[tgt]} save.")
            return
        if k == "de" and info.get("version") != 10:
            self.dest_problem = "older DE save"
            self.dest_notice.show_message("error", "Older Definitive Edition save",
                                          "Load it once in DE 2.0 or Monado and save; that upgrades it.")
            return
        if k not in ("wii", "de", "3ds"):
            self.dest_problem = "not a save"
            self.dest_notice.show_message("error", "Not a Xenoblade Chronicles save", "Choose your save in step 1 "
                                                                                      "first, then a save of the other game.")
            return
        self.dest = {"game": k, "path": os.path.abspath(p), "pending": True}
        self._slot_items()
        if svc.tables_available():            # the preview is read on the worker thread like every engine call
            gen = self._gen
            self.engine.submit(lambda: svc.preview(p), on_done=lambda pv: self._dest_ready(gen, p, pv),
                               on_failed=lambda e, tb: self._dest_failed(gen, p, e))

    def _dest_ready(self, gen, p, pv):
        if gen != self._gen or p != self.dest_pick.path():
            return
        self.dest = pv
        set_text(self.dest_info, short_preview(pv))

    def _dest_failed(self, gen, p, e):
        if gen != self._gen or p != self.dest_pick.path():
            return
        f = explain(e)
        self.dest, self.dest_problem = None, f.title
        self.dest_notice.show_message("error", f.title, f.text, f.detail)
        self.refresh()

    def _slot_items(self):
        d = self.direction()
        self.slot_combo.blockSignals(True)
        self.slot_combo.clear()
        if not d:
            self.slot_combo.setEnabled(False)
            set_text(self.slot_note, "")
            self.slot_combo.blockSignals(False)
            return
        dest = self.dest_pick.path() if self.dest else None
        self.slot_hint = svc.suggest_slot(d, dest)
        names = ([f"bfsgame{i:02d}.sav" for i in range(100)] if TARGET[d] == "de" else
                 ["monado01", "monado02", "monado03"])
        self.slot_combo.addItems(names)
        self.slot_combo.setCurrentText(self._slot_file(self.slot_hint.slot))
        self.slot_combo.setEnabled(True)
        self.slot_combo.blockSignals(False)

    def _slot_file(self, slot):
        return f"bfsgame{slot}.sav" if TARGET.get(self.direction()) == "de" else slot

    def slot(self):
        t = self.slot_combo.currentText()
        return t[7:9] if t.startswith("bfsgame") else t

    # ------------------------------------------------------------------------------------------- history
    def _plan(self):
        """Ask the service how this conversion relates to earlier ones (first / return / needs the user)."""
        if not self.src or self.src.get("pending") or self.src_problem or not svc.tables_available():
            return
        gen, src, d = self._gen, self.src["path"], self.direction()
        dest = self.dest_pick.path() if self.dest and not self.dest_problem else None
        chosen, fresh, folders = self.chosen_record, self.start_fresh, self.history_folders()
        self.plan_pending, self.plan, self.plan_error = True, None, None

        def work():
            plan = svc.resolve_history(src, d, dest, folders, chosen, fresh)
            over = []
            if plan.mode == "first" and d in ("de_to_wii", "de_to_3ds") and dest:
                rep = svc.compatibility(src, dest)
                over = [b for b, v in rep.get("capacity_check", {}).items() if not v["fits"]]
            return plan, over

        self.engine.submit(work, on_done=lambda r: self._planned(gen, r),
                           on_failed=lambda e, tb: self._plan_failed(gen, e, tb))
        self.refresh()

    def _planned(self, gen, r):
        if gen != self._gen:
            return
        self.plan, self.capacity_over = r
        self.plan_pending = False
        p = self.plan
        self.log(f"history: mode={p.mode} issue={p.issue or '-'} record={p.sidecar} dest={p.dest_relation or '-'} "
                 f"similarity={p.similarity}")
        self.adv.set_record_status(
            f"Using {p.sidecar}" if p.sidecar else
            ("First conversion: no earlier record applies." if p.mode == "first" else "Your decision is needed."))
        self.refresh()
        self.plan_ready.emit()

    def _plan_failed(self, gen, e, tb):
        if gen != self._gen:
            return
        self.plan_pending = False
        self.plan_error = explain(e)
        self.last_error = (self.plan_error, tb)
        self.refresh()
        self.plan_ready.emit()

    def choose_conversion(self):
        p = self.plan
        intro = ("More than one earlier conversion matches this save. Choose the one you continued from."
                 if p and p.issue == "choose" else
                 "This save matches an older conversion; a later one exists. Use it only if you are sure "
                 "(the converter still checks your destination save).")
        dlg = ChooseRecordDialog(self, p.choices if p else [], intro)
        if dlg.exec() and dlg.path:
            self.chosen_record = dlg.path
            self.log(f"record chosen: {dlg.path}")
            self._gen += 1
            self._plan()

    def choose_record_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Choose a conversion record", self.history_folders()[0],
                                           RECORD_FILTER)
        if p:
            self.chosen_record, self.start_fresh = p, False
            self._gen += 1
            self._plan()

    def clear_record_choice(self):
        self.chosen_record, self.start_fresh = None, False
        self._gen += 1
        self._plan()

    def confirm_start_fresh(self):
        tgt = GAME[self.target()]
        r = QMessageBox.question(
            self, "Start fresh?",
            f"Convert without the earlier conversion record?\n\nAnything only that record kept (for example items or "
            f"settings only the {tgt} has) will not come back. Your original saves are not changed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Yes:
            self.start_fresh, self.chosen_record = True, None
            self.log("start fresh confirmed")
            self._gen += 1
            self._plan()

    def keep_extra_items(self):
        self.adv.opt_overflow.setChecked(True)     # inputs_changed() follows

    # ------------------------------------------------------------------------------------------- state
    def inputs_changed(self):
        self.refresh()

    def _step2_texts(self):
        tgt = self.target()
        if not tgt:
            self.dest_title.setText("&Destination save")
            self.dest_hint.setText("Used as a starting template. Your existing save won't be changed.")
            return
        self.dest_title.setText(f"&Destination save  ({GAME[tgt]})")
        if self.returning():
            self.dest_hint.setText(f"Your latest {GAME[tgt]} save, checked so no progress is lost. "
                                   "It won't be changed.")
        else:
            self.dest_hint.setText("Used as a starting template. Your existing save won't be changed.")

    def _step2_notice(self):
        """One message for step 2, highest priority first. Returns True when it blocks conversion."""
        if self.dest_problem:
            return True          # shown by _dest_check
        tgt = GAME[self.target()] if self.target() else ""
        p = self.plan
        n = self.dest_notice
        if self.plan_error:
            f = self.plan_error
            n.show_message("error", f.title, f.text, f.detail)
            return True
        if not p:
            n.clear()
            return False
        if p.issue == "choose":
            n.show_message("warn", "More than one earlier conversion matches this save",
                           "Choose the one you continued from.", p.detail,
                           actions=[("Choose conversion…", self.choose_conversion)])
            return True
        if p.issue == "older":
            n.show_message("warn", "This save matches an older conversion",
                           "A later conversion of this playthrough exists. Convert the save from your latest "
                           "conversion instead, or choose deliberately.", p.detail,
                           actions=[("Choose conversion…", self.choose_conversion)])
            return True
        if p.issue == "chosen-invalid":
            n.show_message("error", "The chosen record doesn't belong to this save", "",
                           p.detail, actions=[("Choose another…", self.choose_record_file),
                                              ("Find automatically", self.clear_record_choice)])
            return True
        if p.issue == "dest-unrelated":
            n.show_message("error", f"This {tgt} save is from a different playthrough",
                           f"Choose the {tgt} save you converted from last time, or one you saved after it.")
            return True
        if p.issue == "same-playthrough":
            n.show_message("warn", "No record of your last conversion was found",
                           "These saves look like the same playthrough. Find the folder of your last conversion, "
                           "or start fresh.", f"flag similarity {p.similarity}",
                           actions=[("Find record…", self.choose_record_file), ("Start fresh…",
                                                                               self.confirm_start_fresh)])
            return True
        if self.capacity_over and not self.adv.opt_overflow.isChecked():
            n.show_message("warn", "Your inventory is larger than this Wii save can hold",
                           "Extra unequipped items can be kept for when you return to the Definitive Edition.",
                           ", ".join(self.capacity_over), actions=[("Keep extra items for later",
                                                                   self.keep_extra_items)])
            return True
        if p.mode == "return":
            n.show_message("info", "", f"Continuing your conversion of {when(p.sidecar)}.")
            return False
        if self.start_fresh:
            n.show_message("info", "", "Starting fresh, as you confirmed.")
            return False
        if self.capacity_over:
            n.show_message("info", "", "Extra items will be kept for when you return.")
            return False
        n.clear()
        return False

    def missing(self):
        """The first thing the user still has to do (empty when Convert can run)."""
        tgt = GAME[self.target()] if self.target() else ""
        if not svc.tables_available():
            return "Set up the game data first."
        if self.src_problem:
            return "Choose a different save in step 1."
        if not self.src:
            return "Choose your save."
        if self.src.get("pending"):
            return "Reading your save…"
        if self.compat_problems:
            return "This save can't be converted yet (see step 1)."
        if self.plan_pending:
            return "Checking earlier conversions…"
        no_current = self.adv.opt_no_current.isChecked() and self.returning()
        if self.dest_problem:
            return f"Choose a different {tgt} save in step 2."
        optional = self.direction() == "3ds_to_wii" and not self.returning()   # lossless: no template needed
        if not self.dest_pick.path() and not no_current and not optional:
            return f"Choose a {tgt} save in step 2."
        if self._blocking:
            return "See the message in step 2."
        if not self.out_pick.path():
            return "Choose where to save the converted file."
        if self.out_notice.kind == "error":
            return "Choose another folder in step 3."
        return ""

    def output_dir_for(self, when_=None):
        stamp = (when_ or datetime.datetime.now()).strftime("%Y%m%d-%H%M%S")
        base = os.path.join(self.out_pick.path(), svc.new_output_name(self.direction() or "wii_to_de", stamp))
        out, n = base, 2
        while os.path.lexists(out):
            out, n = f"{base}-{n}", n + 1
        return out

    def refresh(self):
        self._target_items()
        self._src_text()
        self._step2_texts()
        self.out_notice.clear()
        if self.out_pick.path():
            try:
                svc.plan_output(self.output_dir_for(), self.direction() or "wii_to_de",
                                self.slot() if self.direction() else "01")
            except safeio.Refused as e:
                f = explain(e)
                self.out_notice.show_message("error", f.title, f.text, f.detail)
        if self.slot_hint and self.dest:
            used = self.slot_combo.currentText() in [self._slot_file(s) for s in self.slot_hint.used]
            set_text(self.slot_note, "Your save folder already has this name; rename when copying."
                                   if used else "Not used in your save folder.")
        else:
            set_text(self.slot_note, "")
        self._blocking = self._step2_notice() if self.src and not self.src.get("pending") else False
        need = "" if self.running else self.missing()
        busy = self.running
        self.convert_btn.setEnabled(not need and not busy)
        self.convert_btn.setText("Converting…" if busy else "&Convert Save")
        if not busy:
            self.next_label.setText(need)
            self.next_label.setVisible(bool(need))
        for w in (self.src_pick, self.dest_pick, self.out_pick, self.slot_combo, self.drop1, self.drop2,
                  self.adv_btn):
            w.setEnabled(not busy)
        if not busy:
            self.dest_pick.setEnabled(bool(self.src))
            self.slot_combo.setEnabled(bool(self.direction()))
        self.slot_row.setVisible(bool(self.direction()))

    _blocking = False

    # ------------------------------------------------------------------------------------------- conversion
    def build_request(self, out_dir):
        d, src = self.direction(), self.src["path"]
        dest = self.dest_pick.path() or None
        common = dict(out=out_dir, slot=self.slot(), dry_run=self.adv.opt_dry.isChecked())
        if svc.is3(d):
            overflow = "sidecar" if self.adv.opt_overflow.isChecked() else "refuse"
            if self.returning():
                return svc.ThreeDSRequest(direction=d, source=src, record=self.plan.sidecar, current=dest,
                                          no_current=dest is None,
                                          template=dest if svc.TARGET[d] == "3ds" else None,
                                          branch="keep_source" if self.branch else None, overflow=overflow, **common)
            return svc.ThreeDSRequest(direction=d, source=src, template=dest if svc.TARGET[d] != "wii" else None,
                                      overflow=overflow, **common)
        if d == "wii_to_de":
            if self.returning():
                return svc.WiiToDeRequest(wii=src, sidecar=self.plan.sidecar, current_de=dest,
                                          no_current_de=dest is None, branch="wii" if self.branch else None, **common)
            return svc.WiiToDeRequest(wii=src, template=dest, **common)
        overflow = "sidecar" if self.adv.opt_overflow.isChecked() else "refuse"
        if self.returning():
            return svc.DeToWiiRequest(de=src, sidecar=self.plan.sidecar, current_wii=dest,
                                      no_current_wii=dest is None, branch="de" if self.branch else None,
                                      overflow=overflow, **common)
        return svc.DeToWiiRequest(de=src, base=dest, overflow=overflow, same_playthrough=self.adv.opt_same.isChecked(),
                                  **common)

    def _convert_shortcut(self):
        if self.convert_btn.isEnabled() and self.stack.currentIndex() == 0:
            self.start_conversion()

    def start_conversion(self):
        if self.running or self.missing() or self.stack.currentIndex() != 0:
            return False
        self.running = True                  # first: repeated clicks are ignored from here on
        self.convert_btn.setEnabled(False)
        req = self.build_request(self.output_dir_for())
        self.settings.setValue("output_parent", self.out_pick.path())
        self.fail_notice.clear()
        self.log(f"convert: {json.dumps(req.__dict__, default=str)}")
        self.next_label.setText("Reading saves…")
        self.next_label.show()
        self.refresh()
        self.engine.submit(lambda progress: svc.convert_request(req, progress), on_stage=self._stage,
                           on_done=self._converted, on_failed=self._convert_failed, with_progress=True)
        return True

    def _stage(self, key):
        text = dict(svc.STAGES).get(key, key)
        self.next_label.setText(f"{text}…")
        self.log(f"stage: {text}")

    def _converted(self, res):
        self.running = False
        self.branch = False
        self.last_result, self.last_error = res, None
        rep = res.report
        tgt = GAME[TARGET[res.direction]]
        fname = os.path.basename(res.main_output)
        self.res_title.setText("Check complete: nothing was written" if res.dry_run else "Conversion complete")
        self.res_game.setText(tgt)
        self.res_file.setText(os.path.relpath(res.main_output, res.out_dir))
        self.res_folder.setText(res.out_dir)
        self.res_folder.setCursorPosition(0)
        notes = list(rep.get("log", {}).get("warnings", []))
        dfr = {k: v for k, v in rep.get("deferred_to_sidecar", {}).items() if v}
        if dfr:
            notes.append("Kept for your return trip: " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in dfr.items()))
        if notes:
            self.res_warn.show_message("warn", "Please note", "\n".join(notes))
        else:
            self.res_warn.clear()
        if res.dry_run:
            self.res_guide.setText("Turn off \"Check only\" in Advanced to create the file.")
        elif TARGET[res.direction] == "3ds":
            self.res_guide.setText(f"Back up your 3DS saves, then copy {fname} into the game's save folder in Azahar "
                                   "(right-click the game > Open Save Data Location). For a real New 3DS, the "
                                   "checkpoint folder is a complete backup for Checkpoint (not yet tested on "
                                   "hardware). Keep this output folder: it is needed to convert back later.")
        elif TARGET[res.direction] == "de":
            self.res_guide.setText(f"Back up your game's save_0 folder, then copy {fname} (and the .tmb file next to "
                                   "it) into it. Keep this output folder: it is needed to convert back later.")
        else:
            self.res_guide.setText(f"Back up your Wii save slot, then copy {fname} into Dolphin's "
                                   "…\\title\\00010000\\53583445\\data folder. Keep this output folder: it is "
                                   "needed to convert back later.")
        self.open_btn.setVisible(not res.dry_run)
        self.stack.setCurrentIndex(1)
        (self.open_btn if not res.dry_run else self.again_btn).setFocus()
        if not res.dry_run:
            self._remember_folder(self.out_pick.path())
        self.log(f"done: {res.main_output} ({'dry run' if res.dry_run else 'written'}); files: {res.written}")
        self.log(json.dumps(rep, indent=1, default=str))
        self.refresh()
        self.conversion_finished.emit(True)

    def _convert_failed(self, e, tb):
        self.running = False
        self.branch = False
        f = explain(e)
        self.last_result, self.last_error = None, (f, tb)
        msg = str(e)
        actions = []
        if "save also progressed" in msg or "No automatic merge" in msg or "both games were played" in msg:
            actions.append(("Keep this save's progress…", self.confirm_branch))
        elif "exceed the Wii capacity" in msg or "do not fit the Wii box" in msg:
            actions.append(("Keep extra items for later and convert", self._overflow_and_retry))
        elif "looks older" in msg:
            actions.append(("Choose conversion…", self.choose_conversion_any))
        self.fail_notice.show_message("error", f.title, f.text + " Nothing was written.", f.detail, actions)
        self.log(f"stopped: {f.detail}")
        if f.kind == "internal":
            self.log(tb)
        self.refresh()
        self.conversion_finished.emit(False)

    def choose_conversion_any(self):
        self.choose_record_file()

    def _overflow_and_retry(self):
        self.adv.opt_overflow.setChecked(True)
        self.start_conversion()

    def confirm_branch(self):
        src, tgt = GAME[self.src["game"]], GAME[self.target()]
        r = QMessageBox.question(
            self, "Keep this save's progress?",
            f"Both games were played after the last conversion. Convert anyway, keeping the progress of this {src} "
            f"save?\n\nProgress made in the {tgt} after the last conversion will not be in the converted file. "
            "Your original saves are not changed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Yes:
            self.log("keep this save's progress confirmed")
            self.branch = True
            if not self.start_conversion():
                self.branch = False

    def back_to_form(self):
        self.stack.setCurrentIndex(0)
        self.src_pick.set_path("", emit=False)
        self.dest_pick.set_path("", emit=False)
        self.set_source("")
        self.src_pick.edit.setFocus()

    def open_output(self):
        if self.last_result and not self.last_result.dry_run:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_result.out_dir))

    # ------------------------------------------------------------------------------------------- diagnostics
    def diagnostics(self):
        def sh(p):
            try:
                return svc.sha(safeio.read_input(p, "x", limit=40 << 20)) if p and os.path.isfile(p) else None
            except Exception:
                return None

        try:
            data = paths.data_dir()
        except FileNotFoundError:
            data = None
        p = self.plan
        sel = {"source": self.src_pick.path(), "destination": self.dest_pick.path(),
               "output_folder": self.out_pick.path(), "file_name": self.slot_combo.currentText(),
               "check_only": self.adv.opt_dry.isChecked(), "overflow": self.adv.opt_overflow.isChecked(),
               "no_current": self.adv.opt_no_current.isChecked(), "chosen_record": self.chosen_record,
               "start_fresh": self.start_fresh}
        rep = {"app": f"{APP_NAME} {APP_VERSION}", "converter": scmod.CONVERTER_VERSION,
               "python": sys.version.split()[0], "qt": PYSIDE_VERSION, "os": platform.platform(),
               "frozen": bool(getattr(sys, "frozen", False)), "game_data": data, "selection": sel,
               "sha256": {k: sh(sel[k]) for k in ("source", "destination", "chosen_record")},
               "history": None if not p else {"mode": p.mode, "issue": p.issue, "record": p.sidecar,
                                               "destination": p.dest_relation, "similarity": p.similarity,
                                               "choices": [c.path for c in p.choices], "detail": p.detail},
               "last_result": None if not self.last_result else
               {"out_dir": self.last_result.out_dir, "written": self.last_result.written,
                "dry_run": self.last_result.dry_run},
               "last_error": None if not self.last_error else
               {"title": self.last_error[0].title, "detail": self.last_error[0].detail,
                "traceback": self.last_error[1] if self.last_error[0].kind == "internal" else None},
               "log_tail": self._log_lines[-40:]}
        return json.dumps(rep, indent=1, default=str)

    def copy_diagnostics(self):
        self.adv.fill_diag()
        QGuiApplication.clipboard().setText(self.adv.diag_out.toPlainText())
        self.log("diagnostic report copied to the clipboard")

    # ------------------------------------------------------------------------------------------- exit
    def closeEvent(self, e):
        if self.running:
            QMessageBox.information(self, APP_NAME, "A conversion is running. It finishes in a few seconds; nothing "
                                    "is written until it has been verified.")
            e.ignore()
            return
        self.engine.wait(10000)      # a preview or check may still be finishing; they never write
        self.adv.close()
        e.accept()
