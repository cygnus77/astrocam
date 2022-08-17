from datetime import datetime
from pathlib import Path
import os
import tkinter as tk
import tkinter.ttk as ttk
from turtle import bgcolor
import rawpy
from PIL import Image, ImageTk
import time
from multiprocessing import Process, Queue
import queue
from threading import Thread

from argparse import ArgumentParser

#from CameraAPI.CameraAPI import Camera
import numpy as np
import cv2
from Alpaca.camera import Camera, Focuser
from astropy.io import fits
import random

DEFAULT_NUM_EXPS = 5

class DummySnapProcess(Process):
    def __init__(self, cam: Camera, focuser: Focuser, liveview, input_queue, output_queue, destDir):
        super().__init__()
        self.cam = cam
        self.focuser = focuser
        self.liveview = liveview
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.destDir = Path(destDir)

    def run(self):
        try:
            while True:
                exp_job = self.input_queue.get(block=self.liveview)
                if not exp_job:
                    break
                time.sleep(exp_job['exp'])
                fname = random.choice(list(Path(r"C:\code\astrocam\images").glob("*.fit")))
                self.output_queue.put(str(fname))

                if exp_job['focuser_adj']:
                    self.focuser.movein(exp_job['focuser_adj'])

                if 'frame_delay' in exp_job:
                    time.sleep(exp_job['frame_delay'])

        except queue.Empty:
            pass
        finally:
            try:
                self.output_queue.put(None)
            except:
                pass

class SnapProcess(Thread):
    def __init__(self, cam: Camera, focuser: Focuser, liveview, input_queue, output_queue, destDir):
        super().__init__()
        self.cam = cam
        self.focuser = focuser
        self.liveview = liveview
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.destDir = Path(destDir)


    def run(self):
        try:
            while True:
                exp_job = self.input_queue.get(block=self.liveview)
                if not exp_job:
                    break
                self.cam.gain = exp_job['iso']
                self.cam.start_exposure(exp_job['exp'])
                date_obs = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                
                time.sleep(exp_job['exp'])
                while not self.cam.imageready:
                    print('waiting')
                    time.sleep(1)
                img = self.cam.downloadimage()
                temperature = self.cam.temperature

                hdr = fits.Header({
                    'COMMENT': 'Anand Dinakar',
                    'OBJECT': exp_job["object_name"],
                    'INSTRUME': self.cam.name,
                    'DATE-OBS': date_obs,
                    'EXPTIME': exp_job['exp'],
                    'CCD-TEMP': temperature,
                    'XPIXSZ': self.cam.pixelSize[0], #4.63,
                    'YPIXSZ': self.cam.pixelSize[1], #4.63,
                    'XBINNING': self.cam.binning,
                    'YBINNING': self.cam.binning,
                    'XORGSUBF': 0,
                    'YORGSUBF': 0,
                    'BZERO': 0,
                    'BSCALE': 1,
                    'EGAIN': self.cam.egain,
                    'FOCALLEN': exp_job["focal_length"],
                    'SWCREATE': 'AstroCAM',
                    'SBSTDVER': 'SBFITSEXT Version 1.0',
                    'SNAPSHOT': 1,
                    'SET-TEMP': self.cam.set_temp,
                    'IMAGETYP': 'Light Frame',
                    'SITELAT': exp_job["latitude"], #'+40 51 55.000',
                    'SITELONG': exp_job["longitude"], #'-74 20 42.000',
                    'GAIN': exp_job['iso'],
                    'OFFSET': self.cam.offset,
                    'BAYERPAT': self.cam.sensor_type.name
                })

                sno_file = Path('serial_no.txt')
                if sno_file.exists():
                    serial_no = int(sno_file.read_text())
                else:
                    serial_no = 0
                sno_file.write_text(str(serial_no+1))

                output_fname = self.destDir / f"Image{serial_no:05d}_{exp_job['exp']}sec_{exp_job['iso']}gain_{temperature}C.fit"
                hdu = fits.PrimaryHDU(img, header=hdr)
                hdu.writeto(output_fname)

                self.output_queue.put(str(output_fname))

                if exp_job['focuser_adj']:
                    self.focuser.movein(exp_job['focuser_adj'])

                if 'frame_delay' in exp_job:
                    time.sleep(exp_job['frame_delay'])

        except queue.Empty:
            pass
        finally:
            try:
                self.output_queue.put(None)
            except:
                pass


def loadImageHisto(imageFilename, imgCanvasWidth, imgCanvasHeight, histoWidth, histoHeight):
    if imageFilename is None:
        return None
    ext = imageFilename[-3:].lower()
    if ext == 'nef':
        raw = rawpy.imread(imageFilename)
        print(f"Postprocessing {imageFilename}")
        params = rawpy.Params(demosaic_algorithm = rawpy.DemosaicAlgorithm.AHD,
            half_size = False,
            four_color_rgb = False,
            fbdd_noise_reduction=rawpy.FBDDNoiseReductionMode.Off,
            use_camera_wb=True,
            use_auto_wb=False,
            #output_color=rawpy.ColorSpace.raw, 
            #output_bps = 8,
            user_flip = 0,
            no_auto_scale = False,
            no_auto_bright=True
            #highlight_mode= rawpy.HighlightMode.Clip
            )
        rgb = raw.postprocess(params=params)
        raw.close()
        print("Creating PIL image")
        img = Image.fromarray(rgb)

    elif ext == 'fit':
        f = fits.open(imageFilename)
        ph = f[0]
        img = ph.data

        if ph.header['BAYERPAT'] == 'RGGB':
            deb = cv2.cvtColor(img, cv2.COLOR_BAYER_BG2RGB)
            img = deb.astype(np.float32) / np.iinfo(deb.dtype).max
            img = (img * 255).astype(np.uint8)
        img = Image.fromarray(img)

    r, g, b = img.split()

    ##############HISTOGRAM##############
    print("Computing histo")
    red = r.histogram()
    green = g.histogram()
    blue = b.histogram()
    sf_y = histoHeight / max( [max(red),max(green),max(blue)] )
    sf_x = histoWidth / 256

    red_pts = []
    green_pts = []
    blue_pts = []
    for i in range(255):
        red_pts.append(int(i*sf_x))
        red_pts.append(histoHeight-round(red[i] * sf_y))
        green_pts.append(int(i*sf_x))
        green_pts.append(histoHeight-round(green[i] * sf_y))
        blue_pts.append(int(i*sf_x))
        blue_pts.append(histoHeight-round(blue[i] * sf_y))

    params = (img, histoWidth, histoHeight, red_pts, green_pts, blue_pts)
    return params


class AstroCam:
    def __init__(self, cameraModel, destDir):
        self.root = tk.Tk()

        self.windowWidth = self.root.winfo_screenwidth()               
        self.windowHeight = self.root.winfo_screenheight()
        self.root.geometry(f"{self.windowWidth}x{self.windowHeight}")
        self.root.bind("<Configure>", self.resize)
        self.root.bind("<Key>", self.onkeypress)
        self.root.state("zoomed")
        self.camera = Camera(cameraModel)
        self.focuser = Focuser("focus")
        self.destDir = destDir
        self.runStatus = tk.StringVar()
        self.runningExposures = 0
        self.runningLiveView = False
        self.cancelJob = False
        self.imageFilename = None
        self.unscaledImg = None
        self.histoData = None
        self.image_queue = Queue(1000)  
        self.req_queue = Queue(1000)
        self.imageScale = 1.0

        self.cameraTemp = tk.StringVar()
        self.cameraCooler = tk.StringVar()
        self.focuserPos = tk.IntVar()
        self.focuserGotoTgt = tk.IntVar()

        ##############VARIABLES##############
        self.iso_number=tk.IntVar()
        self.iso_number.set(120)
        self.exp_time=tk.DoubleVar()
        self.exp_time.set(1.0)
        self.delay_time = tk.DoubleVar()
        self.delay_time.set(0)
        self.focuser_shift = tk.IntVar()
        self.focuser_shift.set(0)

        self.exposure_number=tk.IntVar()
        self.exposure_number.set(DEFAULT_NUM_EXPS)

        self.EntryFont = ("Segoe UI", 14)
        self.entryWidth = 5
        inactivebgcolor = "#100"
        bgcolor = "#200"
        bgcolor3 = "#300"
        bordercolor = "#500"
        fgcolor = "#d22"
        highlightedcolor = "#800"

        self.root.style = ttk.Style()

        self.root.style.theme_use('clam')
        self.root.style.configure("TButton", padding=2, foreground=fgcolor, background=bgcolor, font=self.EntryFont)
        self.root.style.configure("TFrame", foreground=fgcolor, background=bgcolor)
        self.root.style.configure("TLabel", padding=2, foreground=fgcolor, background=bgcolor, font=self.EntryFont)
        self.root.style.configure("TEntry", padding=2, foreground="black", background=bgcolor, fieldbackground=fgcolor)
        self.root.style.configure("Vertical.TScrollbar", background=bgcolor, bordercolor=bordercolor, arrowcolor=fgcolor, troughcolor=bgcolor)
        self.root.style.configure("Horizontal.TScrollbar", background=bgcolor, bordercolor=bordercolor, arrowcolor=fgcolor, troughcolor=bgcolor)
        self.root.style.configure("X.TButton", padding=0, foreground=fgcolor, background=bgcolor, font=self.EntryFont)

        self.root.style.map("Vertical.TScrollbar",
            background=[("active", bgcolor),("!active", inactivebgcolor),("pressed",highlightedcolor)])
        self.root.style.map("Horizontal.TScrollbar",
            background=[("active", bgcolor),("!active", inactivebgcolor),("pressed",highlightedcolor)])
        

        self.parentFrame=ttk.Frame(self.root, relief=tk.RAISED, borderwidth=1)

        self.imageCanvasFrame = ttk.Frame(self.parentFrame)
        
        self.imageCanvas = tk.Canvas(self.imageCanvasFrame, background="#200")
        self.hbar=ttk.Scrollbar(self.imageCanvasFrame, orient=tk.HORIZONTAL)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.hbar.config(command=self.imageCanvas.xview)
        self.vbar=ttk.Scrollbar(self.imageCanvasFrame, orient=tk.VERTICAL)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.vbar.config(command=self.imageCanvas.yview)
        self.imageCanvas.config(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.imageCanvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        self.imageCanvasFrame.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)

        self.root.wm_attributes('-transparentcolor', '#ab23ff')
        zoomControl = ttk.Frame(self.imageCanvasFrame)
        ttk.Button(zoomControl, text="+", command=self.zoomin, style='X.TButton', width=2).pack(side=tk.RIGHT)
        ttk.Button(zoomControl, text="-", command=self.zoomout, style='X.TButton', width=2).pack(side=tk.RIGHT)
        zoomControl.place(x=5, y=5)#.pack(side=tk.TOP, padx=5, pady=5)


        self.controlPanelFrame = ttk.Frame(self.parentFrame)

        self.histoCanvas=tk.Canvas(self.controlPanelFrame, width=250, height=200, bg='black')
        self.histoCanvas.pack(side=tk.TOP)

        ttk.Label(self.controlPanelFrame, textvariable=self.runStatus).pack(fill=tk.X, side=tk.TOP)

        self.rightControlFrame = ttk.Frame(self.controlPanelFrame)
        self.setupFocuserThermo(self.rightControlFrame)
        self.rightControlFrame.pack(fill=tk.BOTH, side=tk.TOP)

        self.leftControlFrame=ttk.Frame(self.controlPanelFrame)
        self.setupControlBoard(self.leftControlFrame)
        self.leftControlFrame.pack(fill=tk.BOTH, side=tk.BOTTOM)

        self.controlPanelFrame.pack(fill=tk.Y, side=tk.RIGHT)

        self.parentFrame.pack(fill=tk.BOTH, expand=True)

    def setupFocuserThermo(self, frame):
        tempFrame = ttk.Frame(frame)
        ttk.Button(tempFrame, text="Cool", command=self.coolCamera).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Label(tempFrame, textvariable=self.cameraTemp).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(tempFrame, text="Warm", command=self.warmCamera).pack(side=tk.LEFT, padx=5, pady=5)
        tempFrame.pack(fill=tk.X, side=tk.TOP)

        coolerFrame = ttk.Frame(frame)
        ttk.Label(coolerFrame, textvariable=self.cameraCooler).pack(side=tk.LEFT, padx=5, pady=5)
        coolerFrame.pack(fill=tk.X, side=tk.TOP)

        focusFrame = ttk.Frame(frame)
        posFrame = ttk.Frame(focusFrame)
        ttk.Label(posFrame,text="Focuser @").pack(side=tk.LEFT)
        ttk.Label(posFrame,textvariable=self.focuserPos).pack(side=tk.LEFT)
        posFrame.pack(side=tk.LEFT)
        gotoFrame = ttk.Frame(focusFrame)
        ttk.Entry(gotoFrame,textvariable=self.focuserGotoTgt, font=self.EntryFont, width=self.entryWidth).pack(side=tk.RIGHT)
        ttk.Button(gotoFrame, text="Goto", command=self.focuserGoto, style='X.TButton').pack(side=tk.RIGHT)
        gotoFrame.pack(side=tk.RIGHT)
        focusFrame.pack(fill=tk.X, side=tk.TOP)


    def setupControlBoard(self, frame):

        settingsFrame = ttk.Frame(frame)

        settingsRow1 = ttk.Frame(settingsFrame)
        isoFrame = ttk.Frame(settingsRow1)
        ttk.Label(isoFrame,text="ISO").pack(side=tk.LEFT)
        ttk.Entry(isoFrame, textvariable=self.iso_number, font=self.EntryFont, width=self.entryWidth).pack(side=tk.LEFT)
        isoFrame.pack(side=tk.LEFT)

        shutterFrame = ttk.Frame(settingsRow1)
        ttk.Label(shutterFrame,text="Shutter").pack(side=tk.LEFT)
        ttk.Entry(shutterFrame, textvariable=self.exp_time, font=self.EntryFont, width=self.entryWidth).pack(side=tk.LEFT)
        shutterFrame.pack(side=tk.RIGHT)
        settingsRow1.pack(fill=tk.X, side=tk.TOP)

        expFrame = ttk.Frame(settingsFrame)
        ttk.Label(expFrame, text="Subs: ").pack(side=tk.LEFT)
        ttk.Button(expFrame,text="\u2193",command=self.exp_number_down, style='X.TButton', width=2).pack(side=tk.LEFT)
        ttk.Entry(expFrame,textvariable=self.exposure_number, font=self.EntryFont, width=self.entryWidth).pack(side=tk.LEFT)
        ttk.Button(expFrame,text="\u2191",command=self.exp_number_up, style='X.TButton', width=2).pack(side=tk.LEFT)
        expFrame.pack(fill=tk.X, side=tk.TOP)
        
        extrasFrame = ttk.Frame(settingsFrame)
        delayFrame = ttk.Frame(extrasFrame)
        ttk.Label(delayFrame,text="Delay").pack(side=tk.LEFT)
        ttk.Entry(delayFrame, textvariable=self.delay_time, font=self.EntryFont, width=self.entryWidth).pack(side=tk.LEFT)
        delayFrame.pack(fill=tk.X, side=tk.LEFT)

        focusShiftFrame = ttk.Frame(extrasFrame)
        ttk.Label(focusShiftFrame,text="Focus Shift").pack(side=tk.LEFT)
        ttk.Entry(focusShiftFrame, textvariable=self.focuser_shift, font=self.EntryFont, width=self.entryWidth).pack(side=tk.LEFT)
        focusShiftFrame.pack(fill=tk.X, side=tk.RIGHT)

        extrasFrame.pack(fill=tk.X, side=tk.TOP)

        settingsFrame.pack(fill=tk.X, side=tk.TOP, padx=5, pady=5)

        controlFrame = ttk.Frame(frame)
        self.liveviewBtn = ttk.Button(controlFrame,text="LiveView",command=self.liveview)
        self.liveviewBtn.grid(row=0, column=0)
        self.snapshotBtn = ttk.Button(controlFrame,text="Snap",command=self.takeSnapshot)
        self.snapshotBtn.grid(row=0, column=1)
        self.startBtn = ttk.Button(controlFrame,text="Start",command=self.startExps)
        self.startBtn.grid(row=0, column=2)
        ttk.Button(controlFrame,text="Stop", command=self.cancel).grid(row=1, column=2)
        controlFrame.pack(fill=tk.X, side=tk.TOP, padx=5, pady=5)

    def resize(self, event):
        if(event.widget == self.root and
           (self.windowWidth != event.width or self.windowHeight != event.height)):
            print(f'{event.widget=}: {event.height=}, {event.width=}\n')
            self.windowWidth, self.windowHeight = event.width, event.height

            self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))

            # Refit image
            self.displayImage()
            self.displayHistogram()


    def startExps(self):
        print(f"iso={self.iso_number.get()}, exposiure time={self.exp_time.get()}, and number of exposiures:{self.exposure_number.get()} I am sorry about the horrible spmlxivgz!!!!!! I hopee u engoied.")
        self.runningExposures = 1
        self.cancelJob = False
        self.startWorker()

    def takeSnapshot(self):
        print(f"iso={self.iso_number.get()}, exposiure time={self.exp_time.get()}")
        self.exposure_number.set(1)
        self.startWorker()

    def liveview(self):
        print(f"iso={self.iso_number.get()}, exposiure time={self.exp_time.get()}")
        self.cancelJob = False
        self.runningLiveView = True
        self.startLiveViewWorker()


    def endRunningExposures(self, msg):
        self.runningExposures = 0
        self.exposure_number.set(DEFAULT_NUM_EXPS)
        self.runStatus.set(msg)
        self.startBtn["state"] = "normal" 
        self.snapshotBtn["state"] = "normal"
        self.liveviewBtn["state"] = "normal"

    def loadingDone(self, params):

        if self.runningLiveView:
            if self.cancelJob:
                self.endRunningExposures("Stopped Live view")
        elif self.runningExposures:
            if self.cancelJob:
                self.endRunningExposures("Cancelled")
            else:
                self.exposure_number.set(self.exposure_number.get() - 1)
            if self.exposure_number.get() == 0:
                self.endRunningExposures("Finished")
        else:
            self.endRunningExposures("Finished")

        if params is not None:
            self.showImageHisto(*params)


    def startLiveViewWorker(self):
        self.imageFilename = None
        self.startBtn["state"] = "disabled"
        self.snapshotBtn["state"] = "disabled"
        self.liveviewBtn["state"] = "disabled"
        self.runStatus.set("Live view")
        imgCanvasWidth, imgCanvasHeight = int(self.imageCanvas["width"]), int(self.imageCanvas["height"])
        histoWidth, histoHeight = int(self.histoCanvas["width"]), int(self.histoCanvas["height"])

        # Clear request queue
        try:
            while not self.req_queue.empty():
                self.req_queue.get_nowait()
        except queue.Empty:
            pass

        exp_job = {
            "object_name": "M31",
            "focal_length": 1764,
            "latitude": "+40 51 55.000",
            "longitude": "-74 20 42.000",
            "iso": self.iso_number.get(),
            "exp": self.exp_time.get(),
            'focuser_adj':  self.focuser_shift.get(),
            'frame_delay':  self.delay_time.get()
        }

        def threadProc():
            #snapProc = SnapProcess(self.camera, self.focuser, True, self.req_queue, self.image_queue, self.destDir)
            snapProc = DummySnapProcess(self.camera, self.focuser, True, self.req_queue, self.image_queue, self.destDir)
            snapProc.start()
            # Add items for each required exposure
            while not self.cancelJob:
                self.req_queue.put(exp_job)
                # Get filenames from image queue
                fname = self.image_queue.get(block=True)
                # Update UI
                data = loadImageHisto(fname, imgCanvasWidth, imgCanvasHeight, histoWidth, histoHeight)
                self.loadingDone(data)
                
            self.req_queue.put(None)
        # Spawn thread
        Thread(target=threadProc, args=[]).start()

    def startWorker(self):
        self.imageFilename = None
        self.startBtn["state"] = "disabled"
        self.snapshotBtn["state"] = "disabled"
        self.liveviewBtn["state"] = "disabled"
        self.runStatus.set("Taking picture" if self.runningExposures == 0 else "Taking sequence")
        imgCanvasWidth, imgCanvasHeight = int(self.imageCanvas["width"]), int(self.imageCanvas["height"])
        histoWidth, histoHeight = int(self.histoCanvas["width"]), int(self.histoCanvas["height"])

        # Clear request queue
        try:
            while not self.req_queue.empty():
                self.req_queue.get_nowait()
        except queue.Empty:
            pass

        exp_job = {
            "object_name": "M31",
            "focal_length": 1764,
            "latitude": "+40 51 55.000",
            "longitude": "-74 20 42.000",
            "iso": self.iso_number.get(),
            "exp": self.exp_time.get(),
            'focuser_adj':  self.focuser_shift.get(),
            'frame_delay':  self.delay_time.get(),
        }

        # Add items for each required exposure
        try:
            for _ in range(self.exposure_number.get()):
                self.req_queue.put(exp_job)
        except queue.Full:
            pass

        def threadProc():
            # Spawn process
            #snapProc = SnapProcess(self.camera, self.focuser, False, self.req_queue, self.image_queue, self.destDir)
            snapProc = DummySnapProcess(self.camera, self.focuser, False, self.req_queue, self.image_queue, self.destDir)
            snapProc.start()

            # Get filenames from image queue
            while not self.cancelJob:
                fname = self.image_queue.get()
                if fname == None:
                    # Exit if all exposures are done
                    if self.req_queue.empty():
                        break # done
                    else:
                        # Restart child process - it may have crashed
                        while snapProc.is_alive():
                            time.sleep(1)
                        print("Restarting camera proc")
                        #snapProc = SnapProcess(self.camera, self.focuser, False, self.req_queue, self.image_queue, self.destDir)
                        snapProc = DummySnapProcess(self.camera, self.focuser, False, self.req_queue, self.image_queue, self.destDir)
                        snapProc.start()
                else:
                    # Update UI
                    data = loadImageHisto(fname, imgCanvasWidth, imgCanvasHeight, histoWidth, histoHeight)
                    self.loadingDone(data)

        # Spawn thread
        Thread(target=threadProc, args=[]).start()

    def cancel(self):
        self.cancelJob = True
        try:
            while not self.req_queue.empty():
                self.req_queue.get_nowait()
        except queue.Empty:
            pass

    def exp_number_up(self):
        expnum=self.exposure_number.get()
        if expnum < 5:
            newexp = 5
        else:
            newexp = expnum + 5
        self.exposure_number.set(newexp)
        if self.runningExposures:
            exp_job = {
                "object_name": "M31",
                "focal_length": 1764,
                "latitude": "+40 51 55.000",
                "longitude": "-74 20 42.000",
                "iso": self.iso_number.get(),
                "exp": self.exp_time.get(),
                'focuser_adj':  self.focuser_shift.get(),
                'frame_delay':  self.delay_time.get(),
            }
            try:
                for i in range(newexp-expnum):
                    self.req_queue.put(exp_job, block=False)
            except queue.Full:
                pass

    def exp_number_down(self):
        expnum=self.exposure_number.get()
        if expnum <= 5:
            newexp = 5
        else:
            newexp = expnum - 5
        self.exposure_number.set(newexp)
        if self.runningExposures:
            try:
                for i in range(expnum-newexp):
                    self.req_queue.get_nowait(1)
            except queue.Empty:
                pass

    def zoomin(self):
        self.imageScale += 0.5
        self.displayImage()
        self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))

    def zoomout(self):
        self.imageScale -= 0.5
        self.displayImage()
        self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))

    def displayImage(self):
        if self.unscaledImg:
            imgCanvasWidth = self.imageCanvas.winfo_width()
            imgCanvasHeight = self.imageCanvas.winfo_height()
            imgAspect = self.unscaledImg.height / self.unscaledImg.width

            if imgCanvasWidth * imgAspect <= imgCanvasHeight:
                w = imgCanvasWidth
                h = int(imgCanvasWidth * imgAspect)
            else:
                h = imgCanvasHeight
                w = int(imgCanvasHeight / imgAspect)
            self.scaledImg = self.unscaledImg.resize((int(w*self.imageScale), int(h*self.imageScale)), Image.ANTIALIAS)
            self.imageObject = ImageTk.PhotoImage(self.scaledImg)
            self.imageCanvas.delete("all")
            self.imageCanvas.create_image((0,0),image=self.imageObject, anchor='nw')

    def showImageHisto(self, img, histoWidth, histoHeight, red_pts, green_pts, blue_pts):
        self.unscaledImg = img
        self.displayImage()

        self.histoData = [red_pts, green_pts, blue_pts]
        self.displayHistogram()

    def displayHistogram(self):
        if self.histoData:
            self.histoCanvas.delete("all")
            histoCanvasWidth = self.histoCanvas.winfo_width()
            histoCanvasHeight = self.histoCanvas.winfo_height()
            self.histoCanvas.create_rectangle( (0, 0, histoCanvasWidth, histoCanvasHeight), fill="black")
            self.histoCanvas.create_line(self.histoData[0], fill="red")
            self.histoCanvas.create_line(self.histoData[1], fill="lightgreen")
            self.histoCanvas.create_line(self.histoData[2], fill="white")

    def coolCamera(self):
        thread = Thread(target=self.camera.coolto, args=[0])
        thread.start()
    
    def warmCamera(self):
        thread = Thread(target=self.camera.warmto, args=[25])
        thread.start()

    def statusPolling(self):
        self.cameraTemp.set(f"Temp: {self.camera.temperature:.1f} C")
        self.cameraCooler.set(f"Cooler: {'On' if self.camera.cooler == True else 'Off'} power: {self.camera.coolerpower}")
        self.focuserPos.set(self.focuser.position)

        self.root.after(5000, self.statusPolling)

    def startStatusPolling(self):
        self.root.after_idle(self.statusPolling)

    def onkeypress(self, event):
        if event.char == 'i':
            self.focuser.movein(1)
        elif event.char == 'I':
            self.focuser.movein(5)
        elif event.char == 'o':
            self.focuser.moveout(1)
        elif event.char == 'O':
            self.focuser.moveout(5)

    def focuserGoto(self):
        self.focuser.goto(self.focuserGotoTgt.get())

if __name__ == "__main__":

    ap = ArgumentParser()
    ap.add_argument("cameraModel", type=int, choices=[90, 750, 5300, 294])
    args = ap.parse_args()

    destDir = ".\images"
    Path(destDir).mkdir(exist_ok=True)

    astroCam = AstroCam(str(args.cameraModel), destDir)
    astroCam.startStatusPolling()
    astroCam.root.mainloop()
