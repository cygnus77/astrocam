import time
from pathlib import Path
import random
import tkinter as tk
import tkinter.ttk as ttk
import rawpy
from PIL import ImageTk, Image
from astropy.io import fits
import cv2
import numpy as np
from debayer.bilinear import debayer_bilinear
import pandas as pd
from image_data import ImageData
from ui.base_widget import BaseWidget
from scipy.interpolate import interp1d, PchipInterpolator
from image_processing_service import ImageProcessingService


class ImageViewer(BaseWidget):

  def __init__(self, parentFrame, tk_root):
    super().__init__(parentFrame, "RGB Image", collapsed=False, expand=True)
    self.tk_root = tk_root
    self.image = None
    self.imageScale = 1.0
    self.highlights = None
    self.scaledImg = None
    self.starHotSpots = {}
    self.onTargetStarChanged = None

    self.imageProcessingService = ImageProcessingService(tk_root)

    # Image container
    self.imageCanvas = tk.Canvas(self.widgetFrame, background="#200")
    self.image_container = None
    self.crosshairs = None
    self.tooltipLabel = tk.Label(self.imageCanvas, background="#FFFFDD", relief="solid", borderwidth=1)
    self.hbar=ttk.Scrollbar(self.widgetFrame, orient=tk.HORIZONTAL)
    self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
    self.hbar.config(command=self.imageCanvas.xview)
    self.vbar=ttk.Scrollbar(self.widgetFrame, orient=tk.VERTICAL)
    self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
    self.vbar.config(command=self.imageCanvas.yview)
    self.imageCanvas.config(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
    self.imageCanvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    # Bind the mouse click event to the canvas
    self.imageCanvas.bind("<Button-1>", self._onMouseClick)

    # self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    self.gamma = tk.DoubleVar(value=1.0)
    self.gammaStr = tk.StringVar(value="1.0")
    self.updateGammaTable()

    # Buttons
    imageControlPanel = ttk.Frame(self.widgetFrame)
    ttk.Button(imageControlPanel, text="+", command=self.zoomin, style='X.TButton', width=2).pack(side=tk.LEFT)
    ttk.Button(imageControlPanel, text="-", command=self.zoomout, style='X.TButton', width=2).pack(side=tk.LEFT)
    gammaFrame = ttk.Frame(imageControlPanel, width=100)
    ttk.Label(gammaFrame, textvariable=self.gammaStr).pack(side=tk.LEFT)
    ttk.Scale(gammaFrame, from_=0.01, to=5, length=100, variable=self.gamma, command=self.onGammaChange, orient=tk.HORIZONTAL).pack(side=tk.LEFT)
    gammaFrame.pack(side=tk.LEFT)

    self.starbox_enabled = tk.BooleanVar(value=False)
    ttk.Checkbutton(imageControlPanel, text='Starbbox', variable=self.starbox_enabled, command=self.updateStars).pack(side=tk.LEFT)
    imageControlPanel.place(x=5, y=5)

    self.imageCanvas.bind("<Configure>", self.resize)
    self.imageCanvas.bind("<MouseWheel>", self._onMouseWheel)
    self.imageCanvas.bind("<ButtonPress-1>", self._onMousePress)
    self.imageCanvas.bind("<B1-Motion>", self._onMouseDrag)
    self.imageCanvas.bind("<ButtonRelease-1>", self._onMouseRelease)

    # Overlay to show age of the image in seconds since loading
    self.ageLabel = tk.Label(self.imageCanvas, background="#000", foreground="#FFF", font=("Arial", 10), anchor="e")
    self.ageLabel.place(relx=1.0, rely=0.0, x=-10, y=10, anchor="ne")
    self.imageLoadTime = None
    def updateAgeLabel():
      if self.imageLoadTime is not None:
        age_seconds = int(time.time() - self.imageLoadTime)
        self.ageLabel.configure(text=f"{age_seconds}s")
      self.imageCanvas.after(1000, updateAgeLabel)
    updateAgeLabel()

  def _onMouseWheel(self, event):
      if event.delta > 0:
          self.zoomin()
      else:
          self.zoomout()

  def _onMousePress(self, event):
    self.imageCanvas.scan_mark(event.x, event.y)

  def _onMouseDrag(self, event):
      self.imageCanvas.scan_dragto(event.x, event.y, gain=1)

  def _onMouseRelease(self, event):
      pass

  def updateGammaTable(self):
    invGamma = 1.0 / self.gamma.get()
    self.gamma_table = np.array([((i / 255.0) ** invGamma) * 255
      for i in np.arange(0, 256)]).astype("uint8")
    self.gammaStr.set(f"{self.gamma.get():.1f}")

  def set_stretch(self, a1, a2):
    if isinstance(a1, int):
      self.gamma.set(1.0)
      self.gammaStr.set("1.0")
      high = max(a1, a2)
      low = min(a1, a2)
      self.gamma_table = np.zeros((256), dtype=np.uint8)
      self.gamma_table[:low] = 0
      self.gamma_table[high:] = 255
      self.gamma_table[low:high] = np.linspace(0, 255, high-low).astype(np.uint8)
    elif isinstance(a1, list):
      self.gamma_table = np.zeros((256, 3), dtype=np.uint8)
      for i in range(3):
        high = max(a1[i], a2[i])
        low = min(a1[i], a2[i])
        spline = PchipInterpolator([0, low, high, 256], [0, 0, 255, 256])
        self.gamma_table[:, i] = spline(np.arange(256))

  def refresh(self):
    self._refreshDisplay()

  def onGammaChange(self, ev):
    self.updateGammaTable()
    self._refreshDisplay()

  def _scaleImage(self, after):
    if self.image is None:
      return
    imgCanvasWidth, imgCanvasHeight = self.imageCanvas.winfo_width(), self.imageCanvas.winfo_height()
    # print("canvas size: ", imgCanvasWidth, imgCanvasHeight)
    imgAspect = self.image.rgb24.shape[0] / self.image.rgb24.shape[1]

    if imgCanvasWidth * imgAspect <= imgCanvasHeight:
      w = imgCanvasWidth
      h = int(imgCanvasWidth * imgAspect)
    else:
      w = int(imgCanvasHeight / imgAspect)
      h = imgCanvasHeight
    self.scaleX = (w*self.imageScale) / self.image.rgb24.shape[1]
    self.scaleY = (h*self.imageScale) / self.image.rgb24.shape[0]

    def after_resize(j, output):
      scaledImg, imageObject = output
      img = self.scaledImg = scaledImg
      h, w = img.shape[:2]
      self._updatePhotoImage(imageObject, w, h, after)

    self.imageProcessingService.resize(self.image, w, h, self.imageScale, self.gamma_table, on_success=after_resize)
    

  def _refreshDisplay(self, after=None):
    if self.scaledImg is None:
      return
    img = self.scaledImg
    h, w = img.shape[:2]
    self.imageProcessingService.stretch_to_photoimage(img, self.gamma_table, on_success=lambda j, imageObject: self._updatePhotoImage(imageObject, w, h, after))

  def _updatePhotoImage(self, imageObject, w, h, after=None):
    self.imageObject = imageObject
    c_x, c_y = w//2, h//2
    if self.image_container is None:
      self.image_container = self.imageCanvas.create_image((0,0), image=self.imageObject, anchor='nw')
      self.imageCanvas.create_oval(c_x-25, c_y-25, c_x+25, c_y+25, outline="red", tags='crosshairs')
      self.imageCanvas.create_line(c_x-50, c_y, c_x+50, c_y, fill='red', tags='crosshairs')
      self.imageCanvas.create_line(c_x, c_y-50, c_x, c_y+50, fill='red', tags='crosshairs')
    else:
      self.imageCanvas.itemconfig(self.image_container, image=self.imageObject)
      self.imageCanvas.moveto('crosshairs', c_x-25, c_y-25)
    if after is not None:
      self.tk_root.after_idle(after)

  def _updateZoom(self, new_scale):
      old_scale = self.imageScale
      self.imageScale = new_scale
      vw = self.imageCanvas.winfo_width()
      vh = self.imageCanvas.winfo_height()
      # Get center point of canvas in view & update with new scale
      center_x = self.imageCanvas.canvasx(vw//2)
      center_y = self.imageCanvas.canvasy(vh//2)
      center_x = int(center_x * new_scale / old_scale)
      center_y = int(center_y * new_scale / old_scale)
      return max(0, center_x - vw/2), max(0, center_y - vh/2)

  def after_scale(self, scroll_xpos, scroll_ypos):
    self.updateStars()
    self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))
    w, h = self.scaledImg.shape[1], self.scaledImg.shape[0]
    self.imageCanvas.xview_moveto(scroll_xpos/w)
    self.imageCanvas.yview_moveto(scroll_ypos/h)

  def zoomin(self):
    if self.imageScale < 5:
      scroll_xpos, scroll_ypos = self._updateZoom(self.imageScale + 0.5)
      self._scaleImage(after=lambda: self.after_scale(scroll_xpos, scroll_ypos))

  def zoomout(self):
    if self.imageScale > 0.5:
      scroll_xpos, scroll_ypos = self._updateZoom(self.imageScale - 0.5)
      self._scaleImage(after=lambda: self.after_scale(scroll_xpos, scroll_ypos))

  def resize(self, event):
    self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))
    self._scaleImage(after=self.updateStars)

  def _update(self, imgData: ImageData):
    self.image = imgData
    self.imageLoadTime = time.time()
    self._scaleImage(after=self.updateStars)
    return True

  def updateStars(self):
    self.imageCanvas.delete('star_bbox')
    self.starHotSpots = {}
    if self.image is None or self.image.stars is None:
       return
    if not self.starbox_enabled.get():
      return

    def show_tooltip(event, itemid, star):
      x, y, _, _ = self.imageCanvas.coords(itemid)
      self.tooltipLabel.configure(text=f"FWHM: {star.fwhm_x}, {star.fwhm_y}")
      self.tooltipLabel.place(x=x, y=y-20)

    for idx, star in self.image.stars.iterrows():
      sx = int(star['cluster_cx'] * self.scaleX)
      sy = int(star['cluster_cy'] * self.scaleY)
      itemid = self.imageCanvas.create_oval(sx-5, sy-5, sx+5, sy+5, outline="red", tags='star_bbox')
      # self.imageCanvas.tag_bind(itemid, "<Button-1>", lambda evt: show_tooltip(evt, itemid, star))
      # self.imageCanvas.tag_bind(itemid, "<Enter>", lambda evt: show_tooltip(evt, itemid, star))
      self.imageCanvas.tag_bind(itemid, "<Leave>", lambda evt: self.tooltipLabel.place_forget())
      self.starHotSpots[itemid] = star

  def _onMouseClick(self, event):
    if len(self.starHotSpots) == 0:
       return
    h, w = self.scaledImg.shape[:2]
    x = event.x + (w * self.hbar.get()[0])
    y = event.y + (h * self.vbar.get()[0])
    # Perform hit test on ovals
    overlapping_items = self.imageCanvas.find_closest(x, y, 5, max(self.starHotSpots.keys())+1)
    # Check if any oval was hit
    if overlapping_items and overlapping_items[0] in self.starHotSpots:
        # Handle the hit oval
        star = self.starHotSpots[overlapping_items[0]]
        if self.onTargetStarChanged:
           self.onTargetStarChanged(star)
        print(f"Clicked {star}")
        star_name = star['name'] if ('name' in star.index and star['name']) else ""
        self.tooltipLabel.configure(text=f"{star_name}\nFWHM: {star.fwhm_x:.1f}, {star.fwhm_y:.1f}")
        self.tooltipLabel.place(x=event.x, y=event.y-20)
