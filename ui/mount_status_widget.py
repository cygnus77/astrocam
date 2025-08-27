import tkinter as tk
import tkinter.ttk as ttk
from mount_service import MountService
from skymap.skymap import SkyMap
import skymap.platesolver as PS
import psutil
from image_data import ImageData
from ui.base_widget import BaseWidget
from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.coordinates import ICRS
import pandas as pd
from settings import config


class MountStatusWidget(BaseWidget):
    def __init__(self, tk_root, parentFrame, astrocam, device) -> None:
        super().__init__(parentFrame, "Mount")
        self._tk_root = tk_root
        self.mount = device
        self.astrocam = astrocam

        mountFrame = ttk.Frame(self.widgetFrame)
        statusFrame = ttk.Frame(mountFrame)
        # Textbox to show coordinates
        self.radec = tk.StringVar()
        ttk.Label(statusFrame, textvariable=self.radec, font=("TkDefaultFont", 10), wraplength=200).pack(side=tk.TOP)
        # Textbox to show obj name with slightly larger font and multiline
        self.objname = tk.StringVar()
        ttk.Label(statusFrame, textvariable=self.objname, font=("TkDefaultFont", 10), wraplength=200).pack(side=tk.TOP)

        statusFrame.pack(side=tk.TOP)

        gotoFrame = ttk.Frame(mountFrame)
        ttk.Button(gotoFrame, text='Goto...', command=self._goto).pack(side=tk.LEFT)
        ttk.Button(gotoFrame, text='Refine', command=self._refine).pack(side=tk.LEFT)
        gotoFrame.pack(side=tk.TOP)
        mountFrame.pack(fill=tk.X)

    def _on_mount_position_update(self, event):
        mountInfo = self._mount_svc.getMountInfo()
        self.hdrInfo.set(mountInfo['status'])
        self.radec.set(mountInfo['coord_txt'])
        self.objname.set(mountInfo['object_name'])

    def _connect(self, mount, camera_svc):
        self.mount = mount
        self._mount_svc = MountService(self._tk_root, mount, camera_svc)
        self._tk_root.bind(MountService.PositionUpdateEventName, self._on_mount_position_update)

    def _disconnect(self):
        self.mount = None
        self.radec.set("")
        self.objname.set("")
        self._mount_svc.terminate()

    def _goto(self):
        goto_obj_sel = GotoObjectSelector(self, self._mount_svc)
        goto_obj_sel.wait_window()
        if goto_obj_sel.selected_object:
            print(goto_obj_sel.selected_object)
            icrs_deg = goto_obj_sel.selected_object["icrs"]["deg"]
            coord = SkyCoord(icrs_deg["ra"] * u.degree, icrs_deg["dec"] * u.degree, frame=ICRS)
            self._mount_svc.goto(coord)
        return

    def _confirm_ps(self, job, solver_result):
        dlg = RefineConfirm(self, solver_result, self.mount)
        dlg.wait_window()

    def _ps_failed(self, err):
        print(f"Plate solving failed: {err}")

    def _refine(self):
        self._mount_svc.refine(self._confirm_ps, self._ps_failed)

    def platesolve(self, on_completion):
        def apply_ps(job, solver_result):
            self._tk_root.after_idle(lambda: self._mount_svc.syncto(
                                        solver_result['center'], 
                                        on_success=on_completion, 
                                        on_failure=self._ps_failed))
        self._mount_svc.refine(apply_ps, self._ps_failed)


class RefineConfirm(tk.Toplevel):
    def __init__(self, parent, solver_result, device) -> None:
        super().__init__(parent.widgetFrame.winfo_toplevel())
        # set background color of window to bgcolor
        self.configure(bg="#200")

        # set window size to 500x300
        self.geometry("500x500")
        dialog_frame = ttk.Frame(self, padding=10, relief=tk.RAISED, borderwidth=2)

        # Table
        results_frame = ttk.Frame(dialog_frame)
        self.table = ttk.Treeview(results_frame, columns=('Result', 'Info'), show='headings')
        self.table.heading('Result', text='Result')
        self.table.heading('Info', text='Info')
        self.table.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        results_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Insert the new results into the table
        for idx, result_key in enumerate(['solved', 'separation_arcmin', 'num_ref', 'num_tgt', 'solver_votes', 'matches', 'center', 'tx']):
            if result_key in solver_result:
                self.table.insert('', 'end', text=str(idx), values=(result_key, solver_result[result_key]))

        if solver_result['solved']:
            def syncandclose():
                device.syncto(solver_result['center'])
                self.destroy()

            # Select Button
            select_button = ttk.Button(dialog_frame, text="Sync", command=syncandclose)
            select_button.pack(side=tk.BOTTOM)

        dialog_frame.pack(fill=tk.BOTH, expand=True)


class GotoObjectSelector(tk.Toplevel):

  def __init__(self, parent, mount_service) -> None:
    super().__init__(parent.widgetFrame.winfo_toplevel())
    self.selected_object = None
    self._mount_svc = mount_service
    # set background color of window to bgcolor
    self.configure(bg="#200")

    # set window size to 500x300
    self.geometry("500x500")

    dialog_frame = ttk.Frame(self, padding=10, relief=tk.RAISED, borderwidth=2)

    # Term Entry
    search_frame = ttk.Frame(dialog_frame)

    # M number Entry
    m_row = ttk.Frame(search_frame)
    ttk.Label(m_row, text="M:").pack(side=tk.LEFT)
    self.m_search_entry = ttk.Entry(m_row, width=10)
    self.m_search_entry.pack(side=tk.LEFT)
    m_row.pack(side=tk.TOP, fill=tk.X, pady=2)

    # NGC number Entry
    ngc_row = ttk.Frame(search_frame)
    ttk.Label(ngc_row, text="NGC:").pack(side=tk.LEFT)
    self.ngc_search_entry = ttk.Entry(ngc_row, width=10)
    self.ngc_search_entry.pack(side=tk.LEFT)
    ngc_row.pack(side=tk.TOP, fill=tk.X, pady=2)

    # Name Entry
    name_row = ttk.Frame(search_frame)
    ttk.Label(name_row, text="Name:").pack(side=tk.LEFT)
    self.name_search_entry = ttk.Entry(name_row, width=30)
    self.name_search_entry.pack(side=tk.LEFT)
    name_row.pack(side=tk.TOP, fill=tk.X, pady=2)

    # Search Button
    search_button = ttk.Button(search_frame, text="Search", command=self.search)
    search_button.pack(side=tk.TOP, pady=4)

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

    if len(m := self.m_search_entry.get()) > 0:
        results = self._mount_svc.search_catalog('M', m)
    elif len(ngc := self.ngc_search_entry.get()) > 0:
        results = self._mount_svc.search_catalog('NGC', ngc)
    elif len(term := self.name_search_entry.get()) > 0:
        results = self._mount_svc.searchName(term)
    else:
        return

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
