import threading
import tkinter as tk


class ServiceBase(threading.Thread):

    def __init__(self, tk_root):
        super().__init__()
        self._tk_root = tk_root
        self.job = None
        self.output = None
        self.error_message = None
        self._job_avbl = threading.Condition()
        self._processing = threading.Event()
        self._completion_callbacks = []
        self.daemon = True
        self.DoneEventName = f"<<{self.__class__.__name__}Done>>"
        self._tk_root.bind(self.DoneEventName, self._on_job_done)
        self._tk_root.after_idle(self.start)
    
    def terminate(self):
        with self._job_avbl:
            self.job = "terminate"
            self._job_avbl.notify()
        self.join()

    def subscribe(self, cb):
        self._completion_callbacks.append(cb)

    def process(self):
        """ Process job and produce output
        Use time.sleep in polling cycles
        """
        raise NotImplementedError("Subclasses must implement the process() method.")

    def run(self):
        print(f"Started {self.__class__.__name__} thread")
        while True:
            with self._job_avbl:
                self._job_avbl.wait()
                self._processing.set()

            if self.job == "terminate":
                self._processing.clear()
                self.job = None
                return

            try:
                self.process()
                self._tk_root.event_generate(self.DoneEventName, when="tail", x=0)
            except Exception as e:
                self.error_message = f"{self.__class__.__name__}: {e}"
                print(self.error_message)
                self._tk_root.event_generate(self.DoneEventName, when="tail", x=-2)

    def start_job(self, job, on_success=None, on_failure=None):
        if self._job_avbl.acquire(blocking=False):
            if self._processing.is_set():
                self._job_avbl.release()
                return False
            self.job = job
            self._on_success = on_success
            self._on_failure = on_failure
            self._job_avbl.notify()
            self._job_avbl.release()
            return True
        else:
            return False

    def _on_job_done(self, event):
        try:
            if event.x == 0:
                for cb in self._completion_callbacks:
                    cb(self.output)
                if self._on_success is not None:
                    self._on_success(self.job, self.output)
            else:
                if self._on_failure is not None:
                    self._on_failure(self.job, self.error_message)
        finally:
            self._processing.clear()

