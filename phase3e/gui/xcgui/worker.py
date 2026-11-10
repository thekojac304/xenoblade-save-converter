"""Background execution for the GUI.

Every call into the converter engine runs on ONE worker thread (a QThreadPool limited to one thread): the window stays
responsive, and engine calls never run concurrently (the engine's table cache is not thread-safe). Results and
failures come back as Qt signals, which are delivered on the GUI thread.
"""
import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class TaskSignals(QObject):
    stage = Signal(str)
    done = Signal(object)
    failed = Signal(object, str)      # exception, formatted traceback (for the diagnostic report only)


class Task(QRunnable):
    def __init__(self, fn, with_progress=False):
        super().__init__()
        self.fn, self.with_progress = fn, with_progress
        self.signals = TaskSignals()
        self.setAutoDelete(True)

    def run(self):
        try:
            res = self.fn(self.signals.stage.emit) if self.with_progress else self.fn()
        except Exception as e:       # every failure is reported to the window; nothing escapes the thread
            self.signals.failed.emit(e, traceback.format_exc())
            return
        self.signals.done.emit(res)


class Engine(QObject):
    """Single-threaded executor for engine work."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._live = set()

    def submit(self, fn, on_done=None, on_failed=None, on_stage=None, with_progress=False):
        t = Task(fn, with_progress)
        sig = t.signals
        self._live.add(sig)                       # keep the signal object alive until delivery
        if on_stage:
            sig.stage.connect(on_stage)
        if on_done:
            sig.done.connect(on_done)
        if on_failed:
            sig.failed.connect(on_failed)
        sig.done.connect(lambda *_: self._live.discard(sig))
        sig.failed.connect(lambda *_: self._live.discard(sig))
        self.pool.start(t)
        return sig

    def busy(self):
        return self.pool.activeThreadCount() > 0

    def wait(self, ms=-1):
        return self.pool.waitForDone(ms)
