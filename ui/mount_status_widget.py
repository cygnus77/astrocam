import tkinter as tk
import tkinter.ttk as ttk

from ui.base_widget import BaseWidget

GREEN_CHECK = u'\u2713'
EXCLAMATION = u'\u2757'
STOP = u'\u25CF'

class MountStatusWidget(BaseWidget):
    def __init__(self, parentFrame, device) -> None:
        super().__init__()
        self.device = device
        statusFrame = ttk.Frame(parentFrame)
        # Textbox to show coordinates
        self.radec = tk.StringVar()
        ttk.Label(statusFrame, textvariable=self.radec).pack(side=tk.LEFT)
        # Status label indicating status: tracking, park or slewing
        self.statusIcon = tk.StringVar()
        ttk.Label(statusFrame, textvariable=self.statusIcon).pack(side=tk.LEFT)
        statusFrame.pack(side=tk.LEFT)

        self.update()
    
    def update(self):
        if self.device is None:
            return
        if self.device.tracking:
            self.statusIcon.set(GREEN_CHECK)
        elif self.device.atpark:
            self.statusIcon.set(STOP)
        elif self.device.slewing:
            self.statusIcon.set(EXCLAMATION)

        coord = self.device.coordinates
        self.radec.set(coord.to_string("hmsdms"))

    def connect(self, device):
        self.device = device
        self.update()

    def disconnect(self):
        self.device = None
        self.radec.set("")
        self.statusIcon.set(STOP)
