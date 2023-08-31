import time
import tkinter as tk
import tkinter.ttk as ttk
import rawpy
from PIL import ImageTk
from astropy.io import fits
import cv2
import numpy as np
from debayer.bilinear import debayer_bilinear
from debayer.superpixel import debayer_superpixel
import pandas as pd
from image_data import ImageData
from ui.base_widget import BaseWidget

class ImageViewer(BaseWidget):

  def __init__(self, parentFrame):
    super().__init__(parentFrame, "RGB Image", collapsed=False, expand=True)
    self.image = None
    self.imageScale = 1.0
    self.highlights = None
    self.scaledImg = None
    self.starHotSpots = {}
    self.onTargetStarChanged = None

    # Image container
    self.imageCanvas = tk.Canvas(self.widgetFrame, background="#200")
    self.image_container = None
    self.crosshairs = None
    self.tooltipLabel = tk.Label(self.imageCanvas, background="#FFFFDD", relief="solid", borderwidth=1)
    hbar=ttk.Scrollbar(self.widgetFrame, orient=tk.HORIZONTAL)
    hbar.pack(side=tk.BOTTOM, fill=tk.X)
    hbar.config(command=self.imageCanvas.xview)
    vbar=ttk.Scrollbar(self.widgetFrame, orient=tk.VERTICAL)
    vbar.pack(side=tk.RIGHT, fill=tk.Y)
    vbar.config(command=self.imageCanvas.yview)
    self.imageCanvas.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
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
    imageControlPanel.place(x=5, y=5)

    self.imageCanvas.bind("<Configure>", self.resize)

  def updateGammaTable(self):
    invGamma = 1.0 / self.gamma.get()
    self.gamma_table = np.array([((i / 255.0) ** invGamma) * 255
      for i in np.arange(0, 256)]).astype("uint8")
    self.gammaStr.set(f"{self.gamma.get():.1f}")

  def onGammaChange(self, ev):
    self.updateGammaTable()
    self._refreshDisplay()

  def _scaleImage(self):
    if self.image is None:
      return
    imgCanvasWidth, imgCanvasHeight = self.imageCanvas.winfo_width(), self.imageCanvas.winfo_height()
    print(imgCanvasWidth, imgCanvasHeight)
    imgAspect = self.image.rgb24.shape[0] / self.image.rgb24.shape[1]

    if imgCanvasWidth * imgAspect <= imgCanvasHeight:
      w = imgCanvasWidth
      h = int(imgCanvasWidth * imgAspect)
    else:
      w = int(imgCanvasHeight / imgAspect)
      h = imgCanvasHeight
    self.scaleX = (w*self.imageScale) / self.image.rgb24.shape[1]
    self.scaleY = (h*self.imageScale) / self.image.rgb24.shape[0]

    scaledImg = cv2.resize(self.image.rgb24, dsize=(int(w*self.imageScale), int(h*self.imageScale)), interpolation=cv2.INTER_LINEAR)
    if scaledImg.dtype == np.uint16:
      scaledImg = (scaledImg / 256).astype(np.uint8)
    self.scaledImg = scaledImg

  def _refreshDisplay(self):
    if self.scaledImg is None:
      return
    img = self.scaledImg
    # Histogram equalize
    # e_r = cv2.equalizeHist(img[:,:,0])
    # e_g = cv2.equalizeHist(img[:,:,1])
    # e_b = cv2.equalizeHist(img[:,:,2])
    # img = np.stack([e_r, e_g, e_b], axis=2)

    # e_r = self.clahe.apply(img[:,:,0])
    # e_g = self.clahe.apply(img[:,:,1])
    # e_b = self.clahe.apply(img[:,:,2])
    # img = np.stack([e_r, e_g, e_b], axis=2)

    # img = cv2.convertScaleAbs(img, alpha=2.0, beta=50)

    img = cv2.LUT(img, self.gamma_table)

    h, w = img.shape[:2]
    ppm_header = f'P6 {w} {h} 255 '.encode()
    data = ppm_header + img.tobytes()
    self.imageObject = ImageTk.PhotoImage(width=w, height=h, data=data, format='PPM')

    c_x, c_y = w//2, h//2
    if self.image_container is None:
      self.image_container = self.imageCanvas.create_image((0,0), image=self.imageObject, anchor='nw')
      self.imageCanvas.create_oval(c_x-25, c_y-25, c_x+25, c_y+25, outline="red", tags='crosshairs')
      self.imageCanvas.create_line(c_x-50, c_y, c_x+50, c_y, fill='red', tags='crosshairs')
      self.imageCanvas.create_line(c_x, c_y-50, c_x, c_y+50, fill='red', tags='crosshairs')
    else:
      self.imageCanvas.itemconfig(self.image_container, image=self.imageObject)
      self.imageCanvas.moveto('crosshairs', c_x-25, c_y-25)


  def zoomin(self):
    if self.imageScale < 5:
      self.imageScale += 0.5
      self._scaleImage()
      self._refreshDisplay()
      self.updateStars()
      self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))

  def zoomout(self):
    if self.imageScale > 0.5:
      self.imageScale -= 0.5
      self._scaleImage()
      self._refreshDisplay()
      self.updateStars()
      self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))
      
  def resize(self, event):
    self._scaleImage()
    self._refreshDisplay()
    self.updateStars()
    self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))

  def _update(self, imgData: ImageData):

    self.image = imgData
    self._scaleImage()
    self._refreshDisplay()
    return True

  def updateStars(self):
    self.imageCanvas.delete('star_bbox')
    self.starHotSpots = {}
    if self.image is None or self.image.stars is None:
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
    x, y = event.x, event.y
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
        self.tooltipLabel.place(x=x, y=y-20)
