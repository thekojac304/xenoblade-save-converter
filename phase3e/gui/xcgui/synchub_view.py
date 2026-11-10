"""Sync Hub view (Phase 3B): Open -> Scan -> Sync All -> Close.

The view decides nothing about save data: scanning, ancestry, conflicts, conversion, validation, commit and
publication are xcsync calls (the same code the xcsync command line runs), executed on the shared worker thread.
The default view shows plain words only (device, game, location, play time, level); hashes and records stay in
History > Details.
"""
import os
import threading

from PySide6.QtCore import QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton,
                               QScrollArea, QStackedWidget, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

import safeio
from xcsync import store, scan as scanmod, sync as syncmod

from .widgets import Notice, PathPicker, PrimaryButton, label, set_text, soft

GAME = {"wii": "Wii (Dolphin)", "de": "Definitive Edition", "3ds": "Xenoblade 3D"}
STAGE_TEXT = dict(syncmod.STAGES)
STAGE_ORDER = [k for k, _ in syncmod.STAGES]
CONTENT_WIDTH = 720
READY_TEXT = {"current": "ready", "outdated": "older generation", "missing": "not yet published",
              "damaged": "needs publishing again", "not-available": "no output (blocked)", "not-needed": ""}
SYNCTHING_HELP = (
    "<b>How to share the folders with Syncthing</b> (you set this up once in Syncthing yourself):<br>"
    "&bull; For each device, share the folder where its emulator keeps the Xenoblade save <i>from the device</i> "
    "to this PC, and point the device's <b>incoming folder</b> here at it (Settings &gt; Devices).<br>"
    "&bull; Share the device's <b>ready folder</b> <i>from this PC</i> to the device. After a Sync the new save "
    "waits there; copy it into the game on the device (each ready folder has HOW_TO_INSTALL.txt).<br>"
    "&bull; Use <i>Send Only</i> on the sending side and <i>Receive Only</i> on the receiving side if you like; "
    "the Sync Hub never writes into incoming folders and never installs saves into games.<br>"
    "&bull; Android: recent Dolphin versions keep saves in app-private storage that Syncthing cannot reach. Use "
    "Dolphin's own user-folder export/import, or a Dolphin build/setting that keeps the user folder in shared "
    "storage. The New 3DS has no Syncthing: copy files to and from its SD card, and restore with Checkpoint.")


def fmt_time(iso):
    """'2026-11-08T14:18:30' -> '8 Nov 2026, 14:18' (display only)."""
    import datetime
    try:
        t = datetime.datetime.strptime(iso or "", "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return iso or ""
    return f"{t.day} {t:%b %Y, %H:%M}"


def fmt_summary(s):
    if not s:
        return ""
    lv = f"Lv {s['level']}" if s.get("level") else ""
    return " · ".join(x for x in (s.get("location"), f"story {s['story']}", s.get("play_time"), lv) if x)


# ------------------------------------------------------------------------------------------------- dialogs
class DeviceDialog(QDialog):
    def __init__(self, parent, hub, dev=None):
        super().__init__(parent)
        self.hub, self.dev = hub, dev
        self.setWindowTitle("Edit device" if dev else "Add device")
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QComboBox()
        self.name.setEditable(True)
        self.name.addItems([n for n, _ in store.SUGGESTED_DEVICES])
        self.name.setCurrentText(dev["name"] if dev else "")
        self.name.setAccessibleName("Device name")
        self.platform = QComboBox()
        for k in store.PLATFORMS:
            self.platform.addItem(GAME[k], k)
        self.platform.setAccessibleName("Game version on this device")
        self.slot = QComboBox()
        self.slot.setEditable(True)
        self.slot.setAccessibleName("Save slot to publish")
        self.incoming = PathPicker("Choose the folder where this device's saves arrive", mode="dir",
                                   name="incoming folder")
        self.enabled = QCheckBox("Include this device in scans and syncs")
        self.enabled.setChecked(dev.get("enabled", True) if dev else True)
        form.addRow("&Name:", self.name)
        form.addRow("&Game version:", self.platform)
        form.addRow("Incoming &folder:", self.incoming)
        form.addRow("Save &slot:", self.slot)
        form.addRow("", self.enabled)
        lay.addLayout(form)
        self.hint = label("", wrap=True)
        lay.addWidget(self.hint)
        self.err = Notice()
        lay.addWidget(self.err)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.platform.currentIndexChanged.connect(self._plat)
        self.name.currentTextChanged.connect(self._suggest)
        if dev:
            self.platform.setCurrentIndex(store.PLATFORMS.index(dev["platform"]))
            self.platform.setEnabled(False)
            self.incoming.set_path(dev["incoming"], emit=False)
        self._plat()
        if dev:
            self.slot.setCurrentText(dev["slot"])
            self.hint.setText("Ready folder (share it to the device): " + soft(hub.ready_dir(dev)))
        else:
            self.hint.setText("Leave the incoming folder empty to use one inside the Sync Hub folder.")
        self.resize(560, 300)

    def _suggest(self, t):
        for n, plat in store.SUGGESTED_DEVICES:
            if n == t and not self.dev:
                self.platform.setCurrentIndex(store.PLATFORMS.index(plat))

    def _plat(self):
        p = self.platform.currentData()
        self.slot.clear()
        self.slot.addItems(["00", "01", "02"] if p == "de" else ["monado01", "monado02", "monado03"])
        self.slot.setCurrentText(store.DEFAULT_SLOT[p])

    def accept(self):
        try:
            inc = self.incoming.path() or None
            if inc:
                safeio.guard_out(os.path.join(self.hub.root, "x"))   # sanity: the hub itself is fine
                r = os.path.normcase(os.path.abspath(inc))
                for sub in ("ready", "history", "staging", "templates", "metadata"):
                    if r.startswith(os.path.normcase(self.hub.p(sub))):
                        raise store.HubError("an incoming folder cannot be inside the hub's own " + sub + " folder")
            if self.dev:
                self.hub.update_device(self.dev["id"], name=self.name.currentText(), incoming=inc,
                                       slot=self.slot.currentText(), enabled=self.enabled.isChecked())
            else:
                d = self.hub.add_device(self.name.currentText(), self.platform.currentData(), incoming=inc,
                                        slot=self.slot.currentText(), enabled=self.enabled.isChecked())
                self.dev = d
        except (store.HubError, safeio.Refused) as e:
            self.err.show_message("error", "Not saved", str(e))
            return
        super().accept()


class HubSettingsDialog(QDialog):
    """First-run setup and Settings: hub folder, devices, templates, Syncthing help."""

    def __init__(self, parent, view, first_run=False):
        super().__init__(parent)
        self.view = view
        self.setWindowTitle("Sync Hub setup" if first_run else "Sync Hub settings")
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)
        # hub folder
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(label("<b>1. Sync Hub folder</b>"))
        v.addWidget(label("One folder on this PC holds everything the Sync Hub manages: incoming and ready "
                          "folders for each device, the stored templates and every generation (history). Choose an "
                          "empty folder (it is created if needed) or an existing Sync Hub folder. Do not choose a "
                          "game, emulator or save folder."))
        self.folder = PathPicker("Choose the Sync Hub folder", mode="dir", name="Sync Hub folder")
        v.addWidget(self.folder)
        row = QHBoxLayout()
        self.use_btn = QPushButton("&Use this folder")
        self.use_btn.clicked.connect(self._use_folder)
        row.addWidget(self.use_btn)
        row.addStretch(1)
        v.addLayout(row)
        self.folder_note = Notice()
        v.addWidget(self.folder_note)
        v.addStretch(1)
        self.tabs.addTab(w, "Hub &folder")
        # devices
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(label("<b>2. Devices</b> - add only the devices you use; more can be added later."))
        self.dev_list = QTreeWidget()
        self.dev_list.setHeaderLabels(["Device", "Game version", "Incoming folder", "Ready folder"])
        self.dev_list.setRootIsDecorated(False)
        self.dev_list.setAccessibleName("Devices")
        self.dev_list.itemDoubleClicked.connect(lambda *_: self._edit())
        v.addWidget(self.dev_list)
        row = QHBoxLayout()
        for txt, fn in (("&Add device...", self._add), ("&Edit...", self._edit), ("&Remove", self._remove)):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch(1)
        v.addLayout(row)
        self.tabs.addTab(w, "&Devices")
        # templates
        w = QWidget()
        g = QGridLayout(w)
        g.addWidget(label("<b>3. Starting saves / templates</b> - one valid save per game version you use. The "
                          "converter needs it once as a structural template (and the 3DS save picture). A copy is "
                          "stored in the Sync Hub; your file is only read."), 0, 0, 1, 3)
        self.tpl_labels = {}
        for i, p in enumerate(store.PLATFORMS, start=1):
            g.addWidget(label(GAME[p] + ":", bold=True, wrap=False), i, 0)
            lab = label("")
            self.tpl_labels[p] = lab
            g.addWidget(lab, i, 1)
            b = QPushButton("Choose...")
            b.setAccessibleName(f"Choose {GAME[p]} template")
            b.clicked.connect(lambda _=False, p=p: self._template(p))
            g.addWidget(b, i, 2)
        g.setColumnStretch(1, 1)
        g.setRowStretch(len(store.PLATFORMS) + 1, 1)
        self.tpl_note = Notice()
        g.addWidget(self.tpl_note, len(store.PLATFORMS) + 2, 0, 1, 3)
        self.tabs.addTab(w, "&Templates")
        # help
        w = QWidget()
        v = QVBoxLayout(w)
        h = label(SYNCTHING_HELP)
        h.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(h)
        v.addStretch(1)
        self.tabs.addTab(w, "Syncthing &help")
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.accept)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)
        self.resize(760, 460)
        if view.hub:
            self.folder.set_path(view.hub.root, emit=False)
        self.refresh()

    @property
    def hub(self):
        return self.view.hub

    def _use_folder(self):
        p = self.folder.path()
        if not p:
            self.folder_note.show_message("warn", "Choose a folder first")
            return
        try:
            h = store.Hub.create(p)
        except (store.HubError, safeio.Refused, OSError) as e:
            self.folder_note.show_message("error", "This folder cannot be used", str(e))
            return
        self.view.set_hub(h.root, scan=False)
        self.folder_note.show_message("ok", "Sync Hub folder ready", soft(h.root))
        self.refresh()
        self.tabs.setCurrentIndex(1)

    def refresh(self):
        has = self.hub is not None
        for i in (1, 2):
            self.tabs.setTabEnabled(i, has)
        self.dev_list.clear()
        if not has:
            return
        for d in self.hub.devices():
            it = QTreeWidgetItem([d["name"] + ("" if d.get("enabled", True) else " (off)"), GAME[d["platform"]],
                                  d["incoming"], self.hub.ready_dir(d)])
            it.setData(0, Qt.ItemDataRole.UserRole, d["id"])
            self.dev_list.addTopLevelItem(it)
        for c in range(4):
            self.dev_list.resizeColumnToContents(c)
        for p, lab in self.tpl_labels.items():
            try:
                info = self.hub.template_info(p)
                lab.setText(("Stored: " + fmt_summary(info.get("summary"))) if info else "Not set")
            except store.HubError as e:
                lab.setText(str(e))

    def _sel(self):
        it = self.dev_list.currentItem()
        return it.data(0, Qt.ItemDataRole.UserRole) if it else None

    def _add(self):
        if DeviceDialog(self, self.hub).exec():
            self.refresh()

    def _edit(self):
        i = self._sel()
        if i and DeviceDialog(self, self.hub, self.hub.device(i)).exec():
            self.refresh()

    def _remove(self):
        i = self._sel()
        if not i:
            return
        d = self.hub.device(i)
        if QMessageBox.question(self, "Remove device", f"Remove {d['name']} from the Sync Hub? Its folders and the "
                                "history stay on disk.") == QMessageBox.StandardButton.Yes:
            self.hub.remove_device(i)
            self.refresh()

    def _template(self, p):
        f, _ = QFileDialog.getOpenFileName(self, f"Choose a {GAME[p]} save", "",
                                           "Xenoblade saves (monado01 monado02 monado03 bfsgame*.sav);;All files (*)")
        if not f:
            return
        try:
            info = self.hub.add_template(p, f)
            self.tpl_note.show_message("ok", f"{GAME[p]} template stored", fmt_summary(info.get("summary")))
        except Exception as e:                       # every refusal is shown, nothing is stored
            self.tpl_note.show_message("error", "This save cannot be used as a template", str(e))
        self.refresh()


class HistoryDialog(QDialog):
    def __init__(self, parent, view):
        super().__init__(parent)
        self.view = view
        self.setWindowTitle("Sync history")
        lay = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Generation", "Created", "Kind", "From", "Progress", "Platforms"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAccessibleName("Generations")
        self.tree.currentItemChanged.connect(self._show)
        lay.addWidget(self.tree, 2)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setAccessibleName("Generation details")
        lay.addWidget(self.detail, 2)
        row = QHBoxLayout()
        self.rb = QPushButton("&Make this generation current again...")
        self.rb.clicked.connect(self._rollback)
        self.snap = QPushButton("Save a &copy of a kept save...")
        self.snap.clicked.connect(self._snapshot)
        self.open = QPushButton("&Open folder")
        self.open.clicked.connect(self._open)
        for b in (self.rb, self.snap, self.open):
            row.addWidget(b)
        row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)
        self.resize(820, 520)
        self.load()

    def load(self):
        self.tree.clear()
        hub = self.view.hub
        cur = hub.pointer()["current"] if hub.pointer() else None
        self.gens = {g["number"]: g for g in hub.generations()}
        for n in sorted(self.gens, reverse=True):
            g = self.gens[n]
            if g.get("damaged"):
                it = QTreeWidgetItem([str(n), "", "damaged", g["damaged"], "", ""])
            else:
                src = g.get("source") or {}
                kind = g.get("kind", "")
                if kind == "rollback":
                    kind = f"rollback to {g.get('rollback_of')}"
                it = QTreeWidgetItem([f"{n}{'  (current)' if n == cur else ''}", fmt_time(g.get("created")), kind,
                                      f"{src.get('device_name', '')} - {GAME.get(src.get('platform'), '')}",
                                      fmt_summary(src.get("summary")),
                                      ", ".join(store.SHORT[p] for p in sorted(g.get("outputs", {}))) +
                                      (" (partial)" if g.get("partial") else "")])
            it.setData(0, Qt.ItemDataRole.UserRole, n)
            self.tree.addTopLevelItem(it)
        for c in range(6):
            self.tree.resizeColumnToContents(c)
        if self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def _n(self):
        it = self.tree.currentItem()
        return it.data(0, Qt.ItemDataRole.UserRole) if it else None

    def _show(self, *_):
        n = self._n()
        g = self.gens.get(n) if n else None
        if not g or g.get("damaged"):
            self.detail.setPlainText(g.get("damaged", "") if g else "")
            return
        lines = [f"Generation {n} ({g.get('kind')}), created {g.get('created')} by {g.get('app_version')}",
                 f"Source: {g['source'].get('device_name')} ({GAME.get(g['source'].get('platform'))}), "
                 f"{fmt_summary(g['source'].get('summary'))}", f"Folder: {g['_dir']}", ""]
        for p, o in sorted(g.get("outputs", {}).items()):
            lines.append(f"{GAME[p]}: {o.get('from')}")
        for p, why in sorted((g.get("blocked") or {}).items()):
            lines.append(f"{GAME[p]}: NOT produced - {why}")
        for c in g.get("conversions", []):
            lines.append(f"conversion {c['direction']}: {c.get('mode')}")
        lines += [""] + [f"check: {v['check']}" for v in g.get("validation", [])]
        lines += [f"note: {x}" for x in g.get("notes", [])]
        snaps = g.get("snapshots") or []
        if snaps:
            lines.append("")
            lines.append("Saves kept at this sync (recoverable):")
            for s in snaps:
                lines.append(f"  {'[used] ' if s['chosen'] else ''}{s['device_name']}: {s['file']} - "
                             f"{fmt_summary(s.get('summary'))}")
        self.detail.setPlainText("\n".join(lines))
        self.snap.setEnabled(bool(snaps))

    def _rollback(self):
        n = self._n()
        if not n:
            return
        if QMessageBox.question(self, "Make generation current again",
                                f"Make generation {n} the current one again? A new generation is created from it and "
                                "published to the ready folders. Every later generation stays in the history."
                                ) != QMessageBox.StandardButton.Yes:
            return
        self.accept()
        self.view.run_rollback(n)

    def _snapshot(self):
        n = self._n()
        g = self.gens.get(n)
        snaps = (g or {}).get("snapshots") or []
        if not snaps:
            return
        from PySide6.QtWidgets import QInputDialog
        names = [f"{s['device_name']}: {s['file'].split('/')[-1]} - {fmt_summary(s.get('summary'))}" for s in snaps]
        choice, ok = QInputDialog.getItem(self, "Save a copy", "Kept save:", names, 0, False)
        if not ok:
            return
        s = snaps[names.index(choice)]
        parent = QFileDialog.getExistingDirectory(self, "Choose where to put the copy (a new folder is created)")
        if not parent:
            return
        dest = os.path.join(parent, f"xcsync_gen{n:06d}_{s['sha256'][:8]}")
        try:
            p = syncmod.restore_snapshot(self.view.hub, n, s["file"], dest)
            QMessageBox.information(self, "Copy saved", f"Saved to {p}")
        except Exception as e:
            QMessageBox.warning(self, "Not saved", str(e))

    def _open(self):
        n = self._n()
        if n:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.view.hub.gen_dir(n)))


# ------------------------------------------------------------------------------------------------- the view
class SyncHubView(QWidget):
    scan_finished = Signal(object)
    sync_finished = Signal(object)

    def __init__(self, settings=None, engine=None, parent=None, data_setup=None):
        super().__init__(parent)
        from .worker import Engine
        self.settings = settings or QSettings("XCSaveConverter", "XC Save Converter")
        self.engine = engine or Engine(self)
        self.data_setup = data_setup             # callable: open the game-data setup (shared with the converter)
        self.hub = None
        self.result = None                       # last ScanResult
        self.last_sync = None
        self.last_error = None
        self.scanning = self.running = False
        self.choice = None                       # key chosen in a conflict / start choice
        self._cancel = threading.Event()
        self._scan_gen = 0
        self._build()
        h = self.settings.value("sync_hub_folder", "") or ""
        if h and os.path.isfile(os.path.join(h, store.MARKER)):
            self.set_hub(h, scan=False)
        self.refresh()

    # ---- layout
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack)
        self.stack.addWidget(self._wrap(self._welcome_page()))
        self.stack.addWidget(self._wrap(self._main_page()))
        self.stack.addWidget(self._wrap(self._result_page()))
        QShortcut(QKeySequence("F5"), self, activated=self.scan_again)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=lambda: self.sync_btn.isEnabled() and self.start_sync())

    @staticmethod
    def _wrap(inner):
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

    def _welcome_page(self):
        p = QWidget()
        v = QVBoxLayout(p)
        v.addWidget(label("Xenoblade Sync Hub", bold=True, scale=1.6))
        v.addWidget(label("Keep one Xenoblade playthrough across your devices: Wii (Dolphin), Definitive Edition "
                          "(Monado) and Xenoblade 3D. Syncthing moves the files; the Sync Hub finds the newest "
                          "progress and makes matching saves for every game version. It runs only while open."))
        v.addSpacing(8)
        self.welcome_notice = Notice()
        v.addWidget(self.welcome_notice)
        b = PrimaryButton("&Set up Sync Hub...")
        b.clicked.connect(lambda: self.open_settings(first_run=True))
        self.setup_btn = b
        v.addWidget(b)
        o = QPushButton("&Open an existing Sync Hub folder...")
        o.clicked.connect(self._open_existing)
        v.addWidget(o)
        v.addStretch(1)
        return p

    def _main_page(self):
        p = QWidget()
        v = QVBoxLayout(p)
        v.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(label("Xenoblade Sync Hub", bold=True, scale=1.6, wrap=False), 1)
        v.addLayout(head)
        self.status = label("", bold=True, scale=1.2)
        self.status.setAccessibleName("Sync status")
        v.addWidget(self.status)
        self.status_detail = label("")
        v.addWidget(self.status_detail)
        self.notice = Notice()
        v.addWidget(self.notice)
        # the proposed source
        self.src_box = QGroupBox("Newest progress")
        f = QFormLayout(self.src_box)
        self.src_fields = {}
        for k, t in (("device", "Device"), ("game", "Game version"), ("location", "Story location"),
                     ("play_time", "Play time"), ("level", "Character level")):
            lab = label("", selectable=True)
            self.src_fields[k] = lab
            f.addRow(t + ":", lab)
        v.addWidget(self.src_box)
        # a choice (conflict / several starting saves)
        self.choice_box = QGroupBox("Choose which playthrough to continue")
        self.choice_lay = QVBoxLayout(self.choice_box)
        self.choice_group = QButtonGroup(self)
        self.choice_group.buttonClicked.connect(self._chosen)
        v.addWidget(self.choice_box)
        # actions
        row = QHBoxLayout()
        self.sync_btn = PrimaryButton("Sync &All Platforms")
        self.sync_btn.clicked.connect(self.start_sync)
        row.addWidget(self.sync_btn, 2)
        self.scan_btn = QPushButton("Scan &Again")
        self.scan_btn.clicked.connect(self.scan_again)
        row.addWidget(self.scan_btn, 1)
        v.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, len(STAGE_ORDER) - 1)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Sync progress")
        self.stage_label = label("")
        prow = QHBoxLayout()
        prow.addWidget(self.progress, 1)
        self.cancel_btn = QPushButton("&Cancel")
        self.cancel_btn.clicked.connect(self.cancel)
        prow.addWidget(self.cancel_btn)
        v.addLayout(prow)
        v.addWidget(self.stage_label)
        # devices
        v.addWidget(label("Devices", bold=True))
        self.dev_tree = QTreeWidget()
        self.dev_tree.setHeaderLabels(["Device", "Game version", "Status", "Ready folder"])
        self.dev_tree.setRootIsDecorated(False)
        self.dev_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.dev_tree.setAccessibleName("Devices and their status")
        self.dev_tree.setMinimumHeight(120)
        self.dev_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.dev_tree.header().setStretchLastSection(True)
        v.addWidget(self.dev_tree)
        row = QHBoxLayout()
        for txt, fn in (("&Settings", self.open_settings), ("&History", self.open_history),
                        ("&Open Sync Folder", self.open_folder)):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            row.addWidget(b)
            setattr(self, {"&Settings": "settings_btn", "&History": "history_btn",
                           "&Open Sync Folder": "folder_btn"}[txt], b)
        self.publish_btn = QPushButton("&Finish publishing")
        self.publish_btn.clicked.connect(self.finish_publishing)
        row.addWidget(self.publish_btn)
        row.addStretch(1)
        v.addLayout(row)
        self.gen_label = label("")
        v.addWidget(self.gen_label)
        v.addStretch(1)
        return p

    def _result_page(self):
        p = QWidget()
        v = QVBoxLayout(p)
        self.res_title = label("", bold=True, scale=1.4)
        self.res_title.setAccessibleName("Sync result")
        v.addWidget(self.res_title)
        self.res_text = label("", selectable=True)
        v.addWidget(self.res_text)
        self.res_devices = QTreeWidget()
        self.res_devices.setHeaderLabels(["Device", "State", "Ready folder (inside the Sync folder)"])
        self.res_devices.setRootIsDecorated(False)
        self.res_devices.setAccessibleName("Ready folders")
        self.res_devices.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        v.addWidget(self.res_devices)
        self.res_note = label("The files wait in each device's ready folder. Syncthing delivers them when the device "
                              "is online; copying a save into the game on each device is up to you "
                              "(HOW_TO_INSTALL.txt). You can close this window now.")
        v.addWidget(self.res_note)
        row = QHBoxLayout()
        b = PrimaryButton("&Open Sync Folder")
        b.clicked.connect(self.open_folder)
        row.addWidget(b)
        back = QPushButton("&Back to Sync Hub")
        back.clicked.connect(self.back)
        row.addWidget(back)
        row.addStretch(1)
        v.addLayout(row)
        v.addStretch(1)
        return p

    # ---- hub
    def set_hub(self, root, scan=True):
        try:
            self.hub = store.Hub.open(root)
        except store.HubError as e:
            self.hub = None
            self.welcome_notice.show_message("error", "The Sync Hub folder cannot be opened", str(e))
            self.refresh()
            return False
        self.settings.setValue("sync_hub_folder", self.hub.root)
        self.result = None
        self.refresh()
        if scan:
            self.scan_again()
        return True

    def _open_existing(self):
        d = QFileDialog.getExistingDirectory(self, "Open a Sync Hub folder")
        if d:
            self.set_hub(d)

    def start(self):
        """Called when the window is shown: the automatic startup scan."""
        if self.hub and not self.result and not self.scanning:
            self.scan_again()

    # ---- scan
    def scan_again(self):
        if not self.hub or self.running or self.scanning:
            return
        import xcservice
        if not xcservice.tables_available():
            self.notice.show_message("warn", "One-time setup needed",
                                     "The Sync Hub needs the game data tables made from your own copies of the games "
                                     "(the same setup as the converter).",
                                     actions=[("Set up game data...", self.data_setup)] if self.data_setup else ())
            self.refresh()
            return
        self.scanning = True
        self.choice = None
        self._scan_gen += 1
        g = self._scan_gen
        hub = self.hub
        self.refresh()
        self.engine.submit(lambda: scanmod.scan(hub), on_done=lambda r: self._scanned(g, r),
                           on_failed=lambda e, tb: self._scan_failed(g, e, tb))

    def _scanned(self, g, r):
        if g != self._scan_gen:
            return
        self.scanning = False
        self.result = r
        self.last_error = None
        if r.decision.kind in ("start",) or (r.decision.kind == "new-progress" and r.decision.source):
            self.choice = r.decision.source
        self.refresh()
        self.scan_finished.emit(r)

    def _scan_failed(self, g, e, tb):
        if g != self._scan_gen:
            return
        self.scanning = False
        self.result = None
        self.last_error = (e, tb)
        self.notice.show_message("error", "The scan did not finish", str(e), detail=tb)
        self.refresh()
        self.scan_finished.emit(None)

    # ---- choice
    def _chosen(self, btn):
        self.choice = btn.property("key")
        self.refresh()

    def _fill_choices(self, r):
        for b in self.choice_group.buttons():
            self.choice_group.removeButton(b)
            b.deleteLater()
        while self.choice_lay.count():
            it = self.choice_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        if not r or not r.decision.needs_choice:
            self.choice_box.hide()
            return
        self.choice_box.setTitle("Choose the save to start from" if r.decision.kind == "choose-start" else
                                 "Choose which playthrough to continue")
        for k in r.decision.options:
            o = r.find(k)
            s = o.summary or {}
            txt = (f"{o.device_name} - {GAME.get(o.platform)}: {s.get('location', '')}, story {s.get('story')}, "
                   f"{s.get('play_time')}, Lv {s.get('level')}")
            if o.status == "divergent":
                txt += f"  (continues an older sync, generation {o.gen_ref})"
            rb = QRadioButton(txt)
            rb.setProperty("key", k)
            rb.setAccessibleName(txt)
            if k == self.choice:
                rb.setChecked(True)
            self.choice_group.addButton(rb)
            self.choice_lay.addWidget(rb)
        note = label(r.decision.detail or "The save you do not choose is kept in the history; nothing is merged.")
        self.choice_lay.addWidget(note)
        self.choice_box.show()

    # ---- refresh
    def refresh(self):
        if not self.hub:
            self.stack.setCurrentIndex(0)
            return
        if self.stack.currentIndex() == 0:
            self.stack.setCurrentIndex(1)
        r = self.result
        busy = self.scanning or self.running
        if self.scanning:
            self.status.setText("Scanning device folders...")
            set_text(self.status_detail, "Reading saves; nothing is changed.")
        elif r is None:
            self.status.setText("Not scanned yet" if not self.last_error else "The scan did not finish")
            set_text(self.status_detail, "")
        else:
            self.status.setText(r.decision.message)
            set_text(self.status_detail, "" if r.decision.needs_choice else r.decision.detail)
        if r and not self.scanning:
            issues = [i for i in r.issues if i["kind"] != "publish"]
            if r.error:
                self.notice.show_message("error", "The sync history needs attention", r.error)
            elif issues and not self.running:
                self.notice.show_message("info", "Note", issues[0]["text"])
            elif self.notice.kind not in ("error", "warn") or not self.notice.isVisible():
                self.notice.clear()
        self._fill_choices(r if not busy else None)
        src = r.find(self.choice) if (r and self.choice) else None
        self.src_box.setVisible(bool(src))
        if src:
            s = src.summary or {}
            self.src_fields["device"].setText(src.device_name)
            self.src_fields["game"].setText(GAME.get(src.platform, ""))
            self.src_fields["location"].setText(f"{s.get('location', '')} (story {s.get('story')})")
            self.src_fields["play_time"].setText(s.get("play_time") or "")
            self.src_fields["level"].setText(f"{s.get('leader') or ''} Lv {s.get('level')}")
        self.src_box.setTitle("Starting save" if r and r.decision.kind in ("start", "choose-start") else
                              "Selected progress" if r and r.decision.needs_choice else "Newest progress")
        ok = bool(r and src and not busy and not r.error and r.decision.kind in
                  ("start", "choose-start", "new-progress", "conflict"))
        self.sync_btn.setEnabled(ok)
        self.sync_btn.setToolTip("" if ok else "Sync All becomes available when a valid save with new progress is "
                                               "selected")
        self.scan_btn.setEnabled(not busy)
        for b in (self.settings_btn, self.history_btn):
            b.setEnabled(not busy)
        self.history_btn.setEnabled(not busy and bool(self.hub.committed()))
        pub = bool(r and any(i["kind"] == "publish" for i in r.issues))
        self.publish_btn.setVisible(pub and not busy)
        self.progress.setVisible(self.running)
        self.cancel_btn.setVisible(self.running)
        self.stage_label.setVisible(self.running)
        self.dev_tree.clear()
        if r:
            for ds in r.devices:
                d = ds.device
                st = ds.text
                ready = READY_TEXT.get(ds.ready_state, ds.ready_state or "")
                it = QTreeWidgetItem([d["name"], GAME[d["platform"]], st, ready])
                it.setToolTip(2, "\n".join(f"{o.name}: {o.detail or o.note}" for o in ds.saves))
                it.setToolTip(3, self.hub.ready_dir(d))
                self.dev_tree.addTopLevelItem(it)
        else:
            for d in self.hub.devices():
                self.dev_tree.addTopLevelItem(QTreeWidgetItem([d["name"], GAME[d["platform"]], "", ""]))
        gi = r.generation_info if r else None
        set_text(self.gen_label, (f"Last sync: generation {gi['number']}, {fmt_time(gi['created'])}, from "
                                  f"{gi['source'].get('device_name')}" if gi else
                                  "No sync yet." if r else ""))

    # ---- sync
    def _confirm(self, r, o):
        if not r.decision.needs_choice:
            return True
        others = [r.find(k).device_name for k in r.decision.options if k != o.key]
        text = (f"Continue the playthrough from {o.device_name}?\n\n"
                + (f"The progress on {', '.join(dict.fromkeys(others))} will not be in the new saves. " if others else "")
                + "Every save found now is kept in the history and can be recovered; nothing is merged.")
        if o.status == "divergent":
            text += (f"\n\nThis save continues an older sync (generation {o.gen_ref}): progress synced after that "
                     "generation is not in it.")
        return QMessageBox.question(self, "Choose playthrough", text) == QMessageBox.StandardButton.Yes

    def start_sync(self, allow_partial=False, confirm=True):
        r = self.result
        if self.running or self.scanning or not r or not self.choice:
            return
        o = r.find(self.choice)
        if not o or (confirm and not self._confirm(r, o)):
            return
        self.running = True
        self._cancel.clear()
        self.cancel_btn.setEnabled(True)
        self.notice.clear()
        self.progress.setValue(0)
        hub, key = self.hub, self.choice
        self.refresh()
        self.engine.submit(lambda stage: syncmod.sync(hub, r, key, allow_partial=allow_partial, progress=stage,
                                                      cancel=self._cancel.is_set),
                           on_done=self._synced, on_failed=self._sync_failed, on_stage=self._stage,
                           with_progress=True)

    def _stage(self, key):
        if key in STAGE_ORDER:
            self.progress.setValue(STAGE_ORDER.index(key))
            self.stage_label.setText(STAGE_TEXT[key] + "...")
        if key in ("commit", "publish", "done"):
            self.cancel_btn.setEnabled(False)          # past the commit point: nothing to cancel

    def cancel(self):
        self._cancel.set()
        self.cancel_btn.setEnabled(False)
        self.stage_label.setText("Cancelling - nothing will be changed...")

    def _synced(self, res):
        self.running = False
        self.last_sync = res
        self.res_title.setText(res.message if res.complete else
                               ("Partly updated" if res.partial else "Saved, but not every folder was updated"))
        lines = [f"Generation {res.generation}.", f"Sync folder: {self.hub.root}"]
        if not res.complete:
            lines.insert(0, res.message)
        for p, why in sorted(res.blocked.items()):
            lines.append(f"{GAME[p]} not updated: {why}")
        lines += res.notes
        self.res_text.setText(soft("\n".join(lines)))
        self.res_devices.clear()
        for d in self.hub.devices():
            st = res.published.get(d["id"])
            if st is None:
                continue
            txt = {"ready": "Ready (waiting for the device)", "not-available": "Not updated (blocked)"}.get(
                st, "Not updated: " + st.replace("failed: ", ""))
            it = QTreeWidgetItem([d["name"], txt, os.path.relpath(self.hub.ready_dir(d), self.hub.root)])
            it.setToolTip(2, self.hub.ready_dir(d))
            self.res_devices.addTopLevelItem(it)
        self.stack.setCurrentIndex(2)
        self.result = None
        self.refresh()
        self.sync_finished.emit(res)

    def _sync_failed(self, e, tb):
        self.running = False
        self.last_error = (e, tb)
        if isinstance(e, syncmod.Cancelled):
            self.notice.show_message("info", "Sync cancelled", "Nothing was changed.")
        elif isinstance(e, syncmod.Blocked):
            self.notice.show_message(
                "error", "Not every game version can be updated", str(e),
                actions=[("Update the others only...", self._partial)])
        elif isinstance(e, store.HubError) or isinstance(e, safeio.Refused):
            self.notice.show_message("error", "Nothing was synced", str(e))
        else:
            self.notice.show_message("error", "Nothing was synced (unexpected problem)", f"{type(e).__name__}: {e}",
                                     detail=tb)
        self.refresh()
        if isinstance(e, store.HubError) and "Scan Again" in str(e):
            self.result = None
            QTimer.singleShot(0, self.scan_again)
        self.sync_finished.emit(None)

    def _partial(self):
        if QMessageBox.question(
                self, "Update the other game versions only",
                "Update only the game versions that can hold this save? The others keep their previous files and the "
                "generation is marked as partial (not fully synchronised).") == QMessageBox.StandardButton.Yes:
            self.start_sync(allow_partial=True, confirm=False)

    # ---- other actions
    def run_rollback(self, n):
        if self.running:
            return
        self.running = True
        self.notice.clear()
        hub = self.hub
        self.refresh()
        self.engine.submit(lambda stage: syncmod.rollback(hub, n, progress=stage), on_done=self._synced,
                           on_failed=self._sync_failed, on_stage=self._stage, with_progress=True)

    def finish_publishing(self):
        if self.running:
            return
        self.running = True
        hub = self.hub
        self.refresh()

        def done(out):
            self.running = False
            bad = [k for k, v in out.items() if v.startswith("failed")]
            self.notice.show_message("ok" if not bad else "error",
                                     "Ready folders updated" if not bad else "Some ready folders could not be updated",
                                     "\n".join(f"{hub.device(k)['name']}: {v}" for k, v in out.items() if k in bad))
            self.result = None
            self.refresh()
            self.scan_again()

        self.engine.submit(lambda: syncmod.publish(hub), on_done=done, on_failed=self._sync_failed)

    def back(self):
        self.stack.setCurrentIndex(1)
        self.scan_again()

    def open_settings(self, first_run=False):
        dlg = HubSettingsDialog(self, self, first_run=first_run)
        dlg.exec()
        if self.hub:
            self.result = None
            self.refresh()
            self.scan_again()

    def open_history(self):
        if self.hub and self.hub.committed():
            HistoryDialog(self, self).exec()

    def open_folder(self):
        if self.hub:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.hub.root))
