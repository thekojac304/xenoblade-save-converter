"""Top-level window (Phase 3B): two tabs sharing one worker thread.

  Sync Hub          the new on-demand cross-device view (synchub_view.SyncHubView); opens first and scans at start
  Convert one save  the unchanged 3A three-step converter (main_window.MainWindow), embedded as it is
"""
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtWidgets import QMainWindow, QTabWidget

from . import APP_NAME
from .main_window import MainWindow
from .synchub_view import SyncHubView
from .worker import Engine


class Shell(QMainWindow):
    def __init__(self, settings=None):
        super().__init__()
        self.settings = settings or QSettings("XCSaveConverter", "XC Save Converter")
        self.engine = Engine(self)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(520, 440)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.converter = MainWindow(settings=self.settings, engine=self.engine)
        self.converter.setWindowFlags(Qt.WindowType.Widget)
        self.hub_view = SyncHubView(settings=self.settings, engine=self.engine,
                                    data_setup=self._data_setup)
        self.tabs.addTab(self.hub_view, "&Sync Hub")
        self.tabs.addTab(self.converter, "&Convert one save")
        self.setCentralWidget(self.tabs)
        self._started = False

    def _data_setup(self):
        self.tabs.setCurrentWidget(self.converter)
        self.converter.adv.show_tab("data")

    def showEvent(self, e):
        super().showEvent(e)
        if not self._started:
            self._started = True
            QTimer.singleShot(0, self.hub_view.start)       # the automatic startup scan (on the worker thread)

    def busy(self):
        return self.engine.busy() or self.hub_view.scanning or self.hub_view.running or self.converter.running

    def closeEvent(self, e):
        if self.hub_view.running:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, APP_NAME, "A sync is running. Wait until it has finished: a new generation "
                                    "only becomes current after every save has been validated.")
            e.ignore()
            return
        self.converter.closeEvent(e)
        if e.isAccepted():
            self.engine.wait(60000)
