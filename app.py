
import tkinter as tk
import tkinter.ttk as ttk

class AstroApp:
  def __init__(self):
    self.root = tk.Tk()
    # Styling
    self.EntryFont = ("Segoe UI", 14)
    self.entryWidth = 5
    inactivebgcolor = "#100"
    bgcolor = "#200"
    bgcolor3 = "#300"
    bordercolor = "#500"
    fgcolor = "#d22"
    highlightedcolor = "#800"

    # self.root.tk.call('lappend', 'auto_path', './tksvg0.11')
    self.root.tk.call('lappend', 'auto_path', './awthemes-10.4.0')
    self.root.tk.call('source', './awthemes-10.4.0/awdark.tcl')

    self.root.style = ttk.Style()

    self.root.style.theme_use('awdark')
    self.root.style.configure("TButton", padding=2, foreground=fgcolor, background=bgcolor, font=self.EntryFont)
    self.root.style.configure("TProgressbar", troughcolor='black', background=fgcolor, height=1, relief='flat')
    self.root.style.configure("TFrame", foreground=fgcolor, background=bgcolor)
    self.root.style.configure("TLabel", padding=2, foreground=fgcolor, background=bgcolor, font=self.EntryFont)
    self.root.style.configure("TCombobox", padding=2, foreground=fgcolor, background=bgcolor, fieldbackground='black', font=self.EntryFont, width=4)
    self.root.style.configure("TEntry", padding=2, foreground=fgcolor, background=bgcolor, fieldbackground='black')
    self.root.style.configure("Vertical.TScrollbar", background=bgcolor, bordercolor=bordercolor, arrowcolor=fgcolor, troughcolor=bgcolor)
    self.root.style.configure("Horizontal.TScrollbar", background=bgcolor, bordercolor=bordercolor, arrowcolor=fgcolor, troughcolor=bgcolor)
    self.root.style.configure("X.TButton", padding=0, foreground=fgcolor, background=bgcolor, font=self.EntryFont)
    self.root.style.configure("Horizontal.TSlider", background=bgcolor, bordercolor=bordercolor, arrowcolor=fgcolor, troughcolor=bgcolor)
    self.root.style.configure("TCheckbutton", foreground=fgcolor, background=bgcolor, font=self.EntryFont)

    self.root.style.map("Vertical.TScrollbar",
        background=[("active", bgcolor),("!active", inactivebgcolor),("pressed",highlightedcolor)])
    self.root.style.map("Horizontal.TScrollbar",
        background=[("active", bgcolor),("!active", inactivebgcolor),("pressed",highlightedcolor)])
