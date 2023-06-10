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
        statusFrame.pack(side=tk.TOP)

        gotoFrame = ttk.Frame(self.widgetFrame)
        ttk.Button(gotoFrame, text='Goto...', command=self._goto).pack(side=tk.LEFT)
        ttk.Button(gotoFrame, text='Refine', command=self._refine).pack(side=tk.LEFT)
        gotoFrame.pack(side=tk.TOP)

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
            self.hdrInfo.set("Tracking")
        elif self.device.atpark:
            self.hdrInfo.set("Parked")
        elif self.device.slewing:
            self.hdrInfo.set("Slewing")

        coord = self.device.coordinates
        coord_txt = coord.to_string("hmsdms")
        if self.skyMap is not None:
            coord_txt += f" ({self.getName(coord)})"
        self.radec.set(coord_txt)
        return True

    def _connect(self, device):
        self.device = device
        self.update()

    def _disconnect(self):
        self.device = None
        self.radec.set("")

    def getName(self, coord: SkyCoord):
        try:
            if self.skyMap is None:
                return ""
            result = self.skyMap.findObjects(coord, limit=1)
            return result
        except Exception as ex:
            print(f"Failed to get name from SkyMap: {ex}")
            return ""

    def _goto(self):
        if self.skyMap is None:
            return
        goto_obj_sel = GotoObjectSelector(self, self.skyMap)
        goto_obj_sel.wait_window()
        if goto_obj_sel.selected_object:
            print(goto_obj_sel.selected_object)
        return
    
    def _refine(self):
        return


class GotoObjectSelector(tk.Toplevel):
  
  def __init__(self, parent, skymap) -> None:
    super().__init__(parent.widgetFrame.winfo_toplevel())
    self.skymap = skymap
    self.selected_object = None
    # set background color of window to bgcolor
    self.configure(bg="#200")

    # set window size to 500x300
    self.geometry("500x500")

    dialog_frame = ttk.Frame(self, padding=10, relief=tk.RAISED, borderwidth=2)

    # Term Entry
    search_frame = ttk.Frame(dialog_frame)
    ttk.Label(search_frame, text="Name:").pack(side=tk.LEFT)
    self.name_search_entry = ttk.Entry(search_frame, width=30)
    self.name_search_entry.pack(side=tk.LEFT)
    # Search Button
    search_button = ttk.Button(search_frame, text="Search", command=self.search)
    search_button.pack(side=tk.LEFT)
    search_frame.pack(side=tk.TOP, fill=tk.X)

    # Table
    results_frame = ttk.Frame(dialog_frame)
    self.table = ttk.Treeview(results_frame, columns=('Result', 'Info'), show='headings')
    self.table.heading('Result', text='Result')
    self.table.heading('Info', text='Info')
    self.table.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    results_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # Select Button
    select_button = ttk.Button(dialog_frame, text="Select", command=self.select)
    select_button.pack(side=tk.BOTTOM)

    dialog_frame.pack(fill=tk.BOTH, expand=True)

  def search(self):
    results = []
    term = self.name_search_entry.get()
    if len(term) == 0:
        return
    results = self.skymap.searchName(term)

    for i in self.table.get_children():
        self.table.delete(i)
    # Insert the new results into the table
    for idx, result in enumerate(results):
        self.table.insert('', 'end', text=str(idx), values=(result['typ'], result['id']))
    self.results = results

  def select(self):
    # Get the selected item from the table
    selected_item = self.table.selection()
    if selected_item:
        # Retrieve the values of the selected item
        item = self.table.item(selected_item)
        idx = int(item['text'])
        # Perform the necessary action with the selected values
        self.selected_object = self.results[idx]
    # Close the search dialog
    self.destroy()
