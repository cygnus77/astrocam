from datetime import datetime
from pathlib import Path
import sys
import tkinter as tk
import tkinter.ttk as ttk
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
    def __init__(self, cam: Camera, iso, exp, info: dict, input_queue, output_queue, destDir):
        super().__init__()
        self.cam = cam
        self.iso = iso
        self.exp = exp
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.destDir = Path(destDir)
        self.info = info

    def run(self):
        try:
            while self.input_queue.get(block=False):
                time.sleep(self.exp)
                fname = random.choice(list(Path(r"C:\code\astrocam\images").glob("*.fit")))
                self.output_queue.put(str(fname))

        except queue.Empty:
            pass
        finally:
            try:
                self.output_queue.put(None)
            except:
                pass

class SnapProcess(Thread):
    def __init__(self, cam: Camera, focuser: Focuser, input_queue, output_queue, destDir):
        super().__init__()
        self.cam = cam
        self.focuser = focuser
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.destDir = Path(destDir)

    def run(self):
        try:
            while True:
                exp_job = self.input_queue.get(block=False)
                self.cam.gain = exp_job['iso']
                self.cam.start_exposure(exp_job['exp'])
                date_obs = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                
                time.sleep(self.exp)
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

                output_fname = self.destDir / f"Image{serial_no:05d}_{self.exp}sec_{self.iso}gain_{temperature}C.fit"
                hdu = fits.PrimaryHDU(img, header=hdr)
                hdu.writeto(output_fname)

                self.output_queue.put(str(output_fname))

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
        self.expVar=tk.StringVar()
        self.runningExposures = 0
        self.cancelJob = False
        self.imageFilename = None
        self.unscaledImg = None
        self.histoData = None
        self.image_queue = Queue(1000)  
        self.req_queue = Queue(1000)
        self.imageScale = 1.0

        self.cameraTemp = tk.StringVar()
        self.focuserPos = tk.StringVar()

        ##############VARIABLES##############
        self.iso_number=tk.IntVar()
        self.iso_number.set(120)
        self.exp_time=tk.DoubleVar()
        self.exp_time.set(1.0)
        self.delay_time = tk.DoubleVar()
        self.delay_time.set(0)
        self.focuser_shift = tk.IntVar()
        self.focuser_shift.set(2)

        self.exposure_number=tk.IntVar()
        self.exposure_number.set(DEFAULT_NUM_EXPS)

        self.root.style = ttk.Style()
        self.root.style.configure("TButton", padding=6, relief="flat", foreground="#c22", background="#500", font=("Segoe UI", 14, "bold"))
        self.root.style.configure("TFrame", foreground="#c22", background="#500")
        self.root.style.configure("TLabel", foreground="#c22", background="#500", font=("Segoe UI", 14, "bold"))
        self.root.style.configure("TEntry", foreground="#c22", background="#500")
        self.root.style.configure("TScrollbar", foreground="#c22", background="#500")

        self.parentFrame=ttk.Frame(self.root, relief=tk.RAISED, borderwidth=1)

        self.imageCanvasFrame = ttk.Frame(self.parentFrame)
        
        self.imageCanvas = tk.Canvas(self.imageCanvasFrame, background="#500")
        self.hbar=ttk.Scrollbar(self.imageCanvasFrame, orient=tk.HORIZONTAL)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.hbar.config(command=self.imageCanvas.xview)
        self.vbar=ttk.Scrollbar(self.imageCanvasFrame, orient=tk.VERTICAL)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.vbar.config(command=self.imageCanvas.yview)
        self.imageCanvas.config(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.imageCanvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        self.imageCanvasFrame.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)


        self.controlPanelFrame = ttk.Frame(self.parentFrame)

        self.histoCanvas=tk.Canvas(self.controlPanelFrame, width=150, height=150, bg='black')
        self.histoCanvas.pack(side=tk.TOP)

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

        focusFrame = ttk.Frame(frame)
        ttk.Label(focusFrame,textvariable=self.focuserPos).pack(side=tk.LEFT)
        focusFrame.pack(fill=tk.X, side=tk.TOP)


    def setupControlBoard(self, frame):

        settingsFrame = ttk.Frame(frame)

        isoFrame = ttk.Frame(settingsFrame)
        ttk.Label(isoFrame,text="ISO").pack(side=tk.LEFT)
        ttk.Entry(isoFrame, textvariable=self.iso_number, font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        isoFrame.pack(fill=tk.X, side=tk.TOP)

        shutterFrame = ttk.Frame(settingsFrame)
        ttk.Label(shutterFrame,text="Shutter").pack(side=tk.LEFT)
        ttk.Entry(shutterFrame, textvariable=self.exp_time, font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        shutterFrame.pack(fill=tk.X, side=tk.TOP)

        expFrame = ttk.Frame(settingsFrame)
        ttk.Button(expFrame,text="Down \u2193",command=self.exp_number_down).pack(side=tk.LEFT)
        ttk.Label(expFrame,textvariable=self.exposure_number).pack(side=tk.LEFT)
        ttk.Button(expFrame,text="\u2191 Up",command=self.exp_number_up).pack(side=tk.LEFT)
        expFrame.pack(fill=tk.X, side=tk.TOP)
        
        delayFrame = ttk.Frame(settingsFrame)
        ttk.Label(delayFrame,text="Delay").pack(side=tk.LEFT)
        ttk.Entry(delayFrame, textvariable=self.delay_time, font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        delayFrame.pack(fill=tk.X, side=tk.TOP)

        focusShiftFrame = ttk.Frame(settingsFrame)
        ttk.Label(focusShiftFrame,text="Focus Shift").pack(side=tk.LEFT)
        ttk.Entry(focusShiftFrame, textvariable=self.focuser_shift, font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        focusShiftFrame.pack(fill=tk.X, side=tk.TOP)

        settingsFrame.pack(fill=tk.X, side=tk.TOP, padx=5, pady=5)

        controlFrame = ttk.Frame(frame)
        self.snapshotBtn = ttk.Button(controlFrame,text="SNAPSHOT",command=self.takeSnapshot)
        self.snapshotBtn.grid(row=0, column=0)
        self.startBtn = ttk.Button(controlFrame,text="START",command=self.startExps)
        self.startBtn.grid(row=0, column=1)
        ttk.Button(controlFrame,text="Cancel", command=self.cancel).grid(row=1, column=1)
        controlFrame.pack(fill=tk.X, side=tk.TOP, padx=5, pady=5)

        zoomControl = ttk.Frame(frame)
        ttk.Button(zoomControl, text="Zoom+", command=self.zoomin).pack(side=tk.RIGHT)
        ttk.Button(zoomControl, text="Zoom-", command=self.zoomout).pack(side=tk.RIGHT)
        zoomControl.pack(side=tk.TOP, padx=5, pady=5)

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

    def endRunningExposures(self, msg):
        self.runningExposures = 0
        self.exposure_number.set(DEFAULT_NUM_EXPS)
        self.expVar.set(msg)
        self.startBtn["state"] = "normal" 
        self.snapshotBtn["state"] = "normal"

    def loadingDone(self, params):

        if self.runningExposures:
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

    def startWorker(self):
        self.imageFilename = None
        self.startBtn["state"] = "disabled"
        self.snapshotBtn["state"] = "disabled"
        self.expVar.set("Taking picture" if self.runningExposures == 0 else "Taking sequence")
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
            #snapProc = SnapProcess(self.camera, self.req_queue, self.image_queue, self.destDir)
            snapProc = DummySnapProcess(self.camera, self.req_queue, self.image_queue, self.destDir)
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
                        #snapProc = SnapProcess(self.camera, self.req_queue, self.image_queue, self.destDir)
                        snapProc = DummySnapProcess(self.camera, self.req_queue, self.image_queue, self.destDir)
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
            try:
                for i in range(newexp-expnum):
                    self.req_queue.put(1, block=False)
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
            self.imageCanvas.delete("all")
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
        self.focuserPos.set(f"Pos: {self.focuser.position}")
        self.root.after(2000, self.statusPolling)

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

if __name__ == "__main__":

    ap = ArgumentParser()
    ap.add_argument("cameraModel", type=int, choices=[90, 750, 5300, 294])
    args = ap.parse_args()

    destDir = ".\images"
    Path(destDir).mkdir(exist_ok=True)

    astroCam = AstroCam(str(args.cameraModel), destDir)
    astroCam.startStatusPolling()
    astroCam.root.mainloop()
