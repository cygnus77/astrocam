import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox, filedialog
import serial.tools.list_ports
import psutil
import time
from pathlib import Path
import json

class COMPortSelectionDialog(tk.Toplevel):

  def __init__(self, parent) -> None:
    super().__init__(parent)

    # set window size to 500x300
    self.geometry("500x300")

    # set background color of window to bgcolor
    self.configure(bg="#200")

    # Find availalbe COM ports
    comPorts = [port.name for port in serial.tools.list_ports.comports()]
    
    self.comPort = tk.StringVar()

    # create frame and drop-down to select com port
    self.frame = ttk.Frame(self, padding=10, relief=tk.RAISED, borderwidth=2)
    ttk.Label(self.frame, text="Select COM Port").grid(row=0, column=0, sticky=tk.W)
    ttk.OptionMenu(self.frame, self.comPort, None, *comPorts).grid(row=0, column=1, sticky=tk.W)

    # Add OK button
    ttk.Button(self.frame, text="OK", command=self.destroy).grid(row=1, column=0, columnspan=2, sticky=tk.E+tk.W)

    # resize frame to fill window and center
    self.frame.pack(fill=tk.BOTH, expand=True)

    # # center frame in window
    self.frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    # Expand grid to fill frame
    self.frame.columnconfigure(0, weight=1)
    self.frame.columnconfigure(1, weight=1)
    self.frame.rowconfigure(0, weight=1)
    self.frame.rowconfigure(1, weight=1)

    self.title("COM Port Selection")

    if len(comPorts):
      self.comPort.set(comPorts[0])


class EquipmentSelector(tk.Toplevel):
  
  def __init__(self, parent, mount_choices, camera_choices, focuser_choices,
               default_mount:int=0, default_camera:int=0, default_focuser:int=0) -> None:
    super().__init__(parent)
    self.mount = None
    self.camera = None
    self.focuser = None
    self.imageFolder = None

    # set background color of window to bgcolor
    self.configure(bg="#200")

    # set window size to 500x300
    self.geometry("500x300")

    self.mountChoice = tk.StringVar()
    self.cameraChoice = tk.StringVar()
    self.focuserChoice = tk.StringVar()

    self.mountChoice.trace('w', self.onmountChoice)
    self.cameraChoice.trace('w', self.onCameraChoice)
    self.focuserChoice.trace('w', self.onFocuserChoice)

    # Setup frame with drop-downs for mount, camera, focuser
    self.frame = ttk.Frame(self, padding=10, relief=tk.RAISED, borderwidth=2)
    
    ttk.Label(self.frame, text="mount:").grid(row=0, column=0, sticky=tk.W)
    ttk.OptionMenu(self.frame, self.mountChoice, None, *mount_choices).grid(row=0, column=1, sticky=tk.W)
    ttk.Label(self.frame, text="Camera:").grid(row=1, column=0, sticky=tk.W)
    ttk.OptionMenu(self.frame, self.cameraChoice, None, *camera_choices).grid(row=1, column=1, sticky=tk.W)
    ttk.Label(self.frame, text="Focuser:").grid(row=2, column=0, sticky=tk.W)
    ttk.OptionMenu(self.frame, self.focuserChoice, None, *focuser_choices).grid(row=2, column=1, sticky=tk.W)

    # Add OK button
    ttk.Button(self.frame, text="OK", command=self.onOK).grid(row=3, column=0, columnspan=2, sticky=tk.E+tk.W)
   
    # resize frame to fill window and center
    self.frame.pack(fill=tk.BOTH, expand=True)

    # # center frame in window
    self.frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    # Expand grid to fill frame
    self.frame.columnconfigure(0, weight=1)
    self.frame.columnconfigure(1, weight=1)
    self.frame.rowconfigure(0, weight=1)
    self.frame.rowconfigure(1, weight=1)
    self.frame.rowconfigure(2, weight=1)
    self.frame.rowconfigure(3, weight=1)

    # set window title
    self.title("Equipment Selector")

    # Set default values
    self.mountChoice.set(mount_choices[default_mount])
    self.cameraChoice.set(camera_choices[default_camera])
    self.focuserChoice.set(focuser_choices[default_focuser])


  def onmountChoice(self, *args):
    self.mount = self.mountChoice.get()
  
  def onCameraChoice(self, *args):
    self.camera = self.cameraChoice.get()

  def onFocuserChoice(self, *args):
    self.focuser = self.focuserChoice.get()


  def onOK(self):
    if "Ascom" in self.mount+self.camera+self.focuser:
      # Ascom required
      if "RemoteServer.exe" not in [p.name() for p in psutil.process_iter()]:
        p = psutil.Popen(r"RemoteServer.exe", shell=True, cwd=r"C:\Program Files\ASCOM\RemoteServer")
        started = False
        while not started:
          time.sleep(2)
          for p in psutil.process_iter():
            if "RemoteServer.exe" in p.name():
              if len(p.connections()) >= 1:
                started = True
                time.sleep(2)
              break
    self.destroy()

selected_mount_index = 0
selected_camera_index = 0
selected_focuser_index = 0

MOUNT_CHOICES = ['Gemini-Ascom', 'Simulator', 'Simulator-Ascom']
CAMERA_CHOICES = ['ZWO ASI294MC Pro', '294MC-Ascom', 'Nikon D90', 'Nikon D750', 'Simulator']
FOCUSER_CHOICES = ['Celestron-Ascom', 'None', 'Simulator']

def make_camera(camera_name, parent=None):
  # Instantiate selected camera
  if camera_name == "ZWO ASI294MC Pro":
    from asi_native.asinative_camera import ASINativeCamera
    camera = ASINativeCamera("294")
  elif camera_name == "294MC-Ascom":
    from Alpaca.camera import Camera
    camera = Camera("294")
  elif camera_name == "Nikon D90":
    raise NotImplementedError()
  elif camera_name == "Nikon D750":
    raise NotImplementedError()
  elif camera_name == "Simulator":
    from simulated_devices.simulated_camera import SimulatedCamera
    # If simulator is selected, prmompt for folder containing images
    imageFolder = filedialog.askdirectory(title="Select folder containing images", parent=parent)
    camera = SimulatedCamera(imageFolder)
  return camera

def selectEquipment(parent=None):
    global selected_mount_index, selected_camera_index, selected_focuser_index

    if Path("equipment.json").exists():
      with open("equipment.json", "r") as f:
        equipment = json.load(f)
        selected_mount_index = MOUNT_CHOICES.index(equipment["mount"])
        selected_camera_index = CAMERA_CHOICES.index(equipment["camera"])
        selected_focuser_index = FOCUSER_CHOICES.index(equipment["focuser"])

    equipment_selection = EquipmentSelector(parent, MOUNT_CHOICES, CAMERA_CHOICES, FOCUSER_CHOICES, selected_mount_index, selected_camera_index, selected_focuser_index)
    equipment_selection.wait_window()
    selected_mount_index = MOUNT_CHOICES.index(equipment_selection.mount)
    selected_camera_index = CAMERA_CHOICES.index(equipment_selection.camera)
    selected_focuser_index = FOCUSER_CHOICES.index(equipment_selection.focuser)
    print("Mount:", selected_mount_index)
    print("Camera:", selected_camera_index)
    print("Focuser:", selected_focuser_index)

    with open("equipment.json", "w") as f:
      json.dump({"mount": equipment_selection.mount, "camera": equipment_selection.camera, "focuser": equipment_selection.focuser}, f)

    # Instantiate selected mount
    if equipment_selection.mount == "Gemini-Ascom":
      from Alpaca.mount import Mount
      mount = Mount("Gemini")
    elif equipment_selection.mount == "Simulator":
      from simulated_devices.simulated_mount import SimulatedMount
      mount = SimulatedMount()
    elif equipment_selection.mount == "Simulator-Ascom":
      from Alpaca.mount import Mount
      mount = Mount("Simulator")

    camera = make_camera(equipment_selection.camera)

    # Instantiate selected focuser
    if equipment_selection.focuser == "Celestron-Ascom":
        from Alpaca.focuser import Focuser
        focuser = Focuser("Celestron")
    elif equipment_selection.focuser == "None":
        focuser = None
    elif equipment_selection.focuser == "Simulator":
        from simulated_devices.simulated_focuser import SimulatedFocuser
        focuser = SimulatedFocuser()

    return mount, camera, focuser


if __name__ == "__main__":

  selectEquipment()

  # MOUNT_CHOICES = ['Celestron C11', 'AstroTech EDT115']
  # CAMERA_CHOICES = ['294MC-Native', '294MC-Ascom', 'Nikon D90', 'Nikon D750', 'Simulator']
  # FOCUSER_CHOICES = ['Celestron-Native', 'Celestron-Ascom', 'None', 'Simulator']

  # root = tk.Tk()
  # esel = EquipmentSelector(root, MOUNT_CHOICES, CAMERA_CHOICES, FOCUSER_CHOICES)
  # esel.wait_window()

  # print("Mount:", esel.mount)
  # print("Camera:", esel.camera)
  # print("Focuser:", esel.focuser)


  # # if focuser contains native, prompt user for com port and list available com ports
  # if "native" in esel.focuser.lower():
  #   comsel = COMPortSelectionDialog(root)
  #   comsel.wait_window()
  #   print(comsel.comPort.get())
