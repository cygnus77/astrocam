import tkinter as tk
import tkinter.ttk as ttk

from ui.base_widget import BaseWidget

class FocuserWidget(BaseWidget):
  def __init__(self, parentFrame, device):
    super().__init__()

    self.focuserPos = tk.IntVar()
    self.focuserGotoTgt = tk.IntVar()

    self.focuser = device
    posFrame = ttk.Frame(parentFrame)
    ttk.Label(posFrame,text="Focuser @").pack(side=tk.LEFT)
    ttk.Label(posFrame,textvariable=self.focuserPos).pack(side=tk.LEFT)
    posFrame.pack(side=tk.LEFT)
    gotoFrame = ttk.Frame(parentFrame)
    ttk.Entry(gotoFrame,textvariable=self.focuserGotoTgt, font=BaseWidget.EntryFont, width=BaseWidget.EntryWidth).pack(side=tk.RIGHT)
    ttk.Button(gotoFrame, text="Goto", command=self.focuserGoto, style='X.TButton').pack(side=tk.RIGHT)
    gotoFrame.pack(side=tk.RIGHT)

  def focuserGoto(self):
    self.focuser.goto(self.focuserGotoTgt.get())

  def onkeypress(self, event):
    if event.char == 'i':
      self.focuser.movein(1)
    elif event.char == 'I':
      self.focuser.movein(5)
    elif event.char == 'o':
      self.focuser.moveout(1)
    elif event.char == 'O':
      self.focuser.moveout(5)

  def update(self):
    self.focuserPos.set(self.focuser.position)

