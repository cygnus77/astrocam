import tkinter as tk
import tkinter.ttk as ttk
from skymap.skymap import SkyMap
import psutil
from ui.base_widget import BaseWidget
from astropy.coordinates import SkyCoord
import requests
from settings import config


class MountStatusWidget(BaseWidget):
    def __init__(self, parentFrame, device) -> None:
        super().__init__(parentFrame, "Mount")
        self._connectSkyMap()
        self.device = device
        statusFrame = ttk.Frame(self.widgetFrame)
        # Textbox to show coordinates
        self.radec = tk.StringVar()
        ttk.Label(statusFrame, textvariable=self.radec).pack(side=tk.LEFT)
        # Status label indicating status: tracking, park or slewing
        self.statusIcon = tk.StringVar()
        ttk.Label(statusFrame, textvariable=self.statusIcon).pack(side=tk.LEFT)
        statusFrame.pack(side=tk.LEFT)

        self.update()
    
    def _connectSkyMap(self):
        try:
            if "mongod.exe" not in [p.name() for p in psutil.process_iter()]:
                psutil.Popen([r"mongod.exe", "--dbpath", config['stardb']], shell=True, cwd=config['mongodir'])
            self.skyMap = SkyMap()
        except Exception as ex:
            print(f"Failed to connect to SkyMap: {ex}")
            self.skyMap = None

    def _update(self):
        if self.device is None:
            return False
        if self.device.tracking:
            self.statusIcon.set(BaseWidget.GREEN_CHECK)
        elif self.device.atpark:
            self.statusIcon.set(BaseWidget.STOP)
        elif self.device.slewing:
            self.statusIcon.set(BaseWidget.EXCLAMATION)

        coord = self.device.coordinates
        coord_txt = coord.to_string("hmsdms")
        if self.skyMap is not None:
            coord_txt += f" ({self.getName(coord)})"
        self.radec.set(coord_txt)
        return

    def _connect(self, device):
        self.device = device
        self.update()

    def _disconnect(self):
        self.device = None
        self.radec.set("")
        self.statusIcon.set(BaseWidget.STOP)

    def getName(self, coord: SkyCoord):
        try:
            if self.skyMap is None:
                return ""
            result = self.skyMap.findObjects(coord, limit=1)
            return result
        except Exception as ex:
            print(f"Failed to get name from SkyMap: {ex}")
            return ""
