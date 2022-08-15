from datetime import datetime
from pathlib import Path
import sys
import tkinter
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
    def __init__(self, cam: Camera, focuser: Focuser, iso, exp, info: dict, input_queue, output_queue, destDir):
        super().__init__()
        self.cam = cam
        self.focuser = focuser
        self.iso = iso
        self.exp = exp
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.destDir = Path(destDir)
        self.info = info

    def run(self):
        try:
            while self.input_queue.get(block=False):
                self.cam.gain = self.iso
                self.cam.start_exposure(self.exp)
                date_obs = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                
                time.sleep(self.exp)
                while not self.cam.imageready:
                    print('waiting')
                    time.sleep(1)
                img = self.cam.downloadimage()
                temperature = self.cam.temperature

                hdr = fits.Header({
                    'COMMENT': 'Anand Dinakar',
                    'OBJECT': self.info["object_name"],
                    'INSTRUME': self.cam.name,
                    'DATE-OBS': date_obs,
                    'EXPTIME': self.exp,
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
                    'FOCALLEN': self.info["focal_length"],
                    'SWCREATE': 'AstroCAM',
                    'SBSTDVER': 'SBFITSEXT Version 1.0',
                    'SNAPSHOT': 1,
                    'SET-TEMP': self.cam.set_temp,
                    'IMAGETYP': 'Light Frame',
                    'SITELAT': self.info["latitude"], #'+40 51 55.000',
                    'SITELONG': self.info["longitude"], #'-74 20 42.000',
                    'GAIN': self.iso,
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

                self.focuser.movein(2)

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
        self.root = tkinter.Tk()

        self.windowWidth = self.root.winfo_screenwidth()               
        self.windowHeight = self.root.winfo_screenheight()
        #self.root.attributes('-fullscreen', True)
        self.root.geometry(f"{self.windowWidth}x{self.windowHeight}")
        self.root.bind("<Configure>", self.resize)
        self.root.state("zoomed")
        self.camera = Camera(cameraModel)
        self.camera = Focuser("focus")
        self.destDir = destDir
        self.expVar=tkinter.StringVar()
        self.runningExposures = 0
        self.cancelJob = False
        self.imageFilename = None
        self.unscaledImg = None
        self.histoData = None
        self.image_queue = Queue(1000)  
        self.req_queue = Queue(1000)
        self.imageScale = 1.0

        self.cameraTemp = tkinter.StringVar()
        self.focuserPos = tkinter.StringVar()

        self.info = {
            "object_name": "M31",
            "focal_length": 1764,
            "latitude": "+40 51 55.000",
            "longitude": "-74 20 42.000"
        }

        ##############VARIABLES##############
        self.iso_number=tkinter.IntVar()
        self.iso_number.set(120)
        self.exp_time=tkinter.DoubleVar()
        self.exp_time.set(1.0)

        self.exposure_number=tkinter.IntVar()
        self.exposure_number.set(DEFAULT_NUM_EXPS)
        self.parentFrame=tkinter.Frame(self.root)

        col0w = round(0.80 * self.windowWidth)
        col1w = self.windowWidth - col0w
        row0h = round(0.10 * self.windowHeight)
        row1h = round(0.10 * self.windowHeight)
        row2h = self.windowHeight - (row0h+row1h)

        self.leftControlFrame=tkinter.Frame(self.parentFrame,height =row0h,width = col0w)
        self.leftControlFrame.grid(row=0,column=0,sticky=tkinter.W)

        self.histoCanvas=tkinter.Canvas(self.parentFrame,height=row0h+row1h, width=col1w, borderwidth=0, highlightthickness=0)
        self.histoCanvas.grid(row=0,column=1,rowspan=2, sticky=tkinter.N)

        self.imageCanvasFrame=tkinter.Frame(self.parentFrame,height=(row1h+row2h), width=col0w)
        self.imageCanvasFrame.grid(row=1,column=0,rowspan=2,sticky=tkinter.W)

        self.imageCanvas = tkinter.Canvas(self.imageCanvasFrame, height=(row1h+row2h), width=col0w, borderwidth=0, highlightthickness=0, scrollregion=(0,0,col0w,row1h+row2h))
        self.hbar=tkinter.Scrollbar(self.imageCanvasFrame, orient=tkinter.HORIZONTAL)
        self.hbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        self.hbar.config(command=self.imageCanvas.xview)
        self.vbar=tkinter.Scrollbar(self.imageCanvasFrame, orient=tkinter.VERTICAL)
        self.vbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        self.vbar.config(command=self.imageCanvas.yview)
        self.imageCanvas.config(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.imageCanvas.pack(side=tkinter.LEFT, expand=True, fill=tkinter.BOTH)

        self.rightControlFrame=tkinter.Frame(self.parentFrame,height=row2h, width=col1w)
        self.rightControlFrame.grid(row=2,column=1,sticky=tkinter.E)

        self.parentFrame.pack(expand=False)

    def resize(self, event):
        if(event.widget == self.root and
           (self.windowWidth != event.width or self.windowHeight != event.height)):
            print(f'{event.widget=}: {event.height=}, {event.width=}\n')
            self.windowWidth, self.windowHeight = event.width, event.height
            col0w = round(0.80 * self.windowWidth)
            col1w = self.windowWidth - col0w
            row0h = round(0.10 * self.windowHeight)
            row1h = round(0.10 * self.windowHeight)
            row2h = self.windowHeight - (row0h+row1h)

            self.leftControlFrame.config(height =row0h,width = col0w)
            self.histoCanvas.config(height=row0h+row1h, width=col1w)
            self.imageCanvasFrame.config(height=(row1h+row2h), width=col0w)
            self.imageCanvas.config(height=(row1h+row2h), width=col0w)
            self.imageCanvas.configure(scrollregion=self.imageCanvas.bbox("all"))
            self.rightControlFrame.config(height=row2h, width=col1w)

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

        # Add items for each required exposure
        try:
            for _ in range(self.exposure_number.get()):
                self.req_queue.put(1)
        except queue.Full:
            pass

        def threadProc(iso, exp):
            # Spawn process
            #snapProc = SnapProcess(self.camera, iso, exp, self.info, self.req_queue, self.image_queue, self.destDir)
            snapProc = DummySnapProcess(self.camera, iso, exp, self.info, self.req_queue, self.image_queue, self.destDir)
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
                        #snapProc = SnapProcess(self.camera, iso, exp, self.req_queue, self.image_queue, self.destDir)
                        snapProc = DummySnapProcess(self.camera, iso, exp, self.info, self.req_queue, self.image_queue, self.destDir)
                        snapProc.start()
                else:
                    # Update UI
                    data = loadImageHisto(fname, imgCanvasWidth, imgCanvasHeight, histoWidth, histoHeight)
                    self.loadingDone(data)

        # Spawn thread
        Thread(target=threadProc, args=[self.iso_number.get(), self.exp_time.get()]).start()

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

    def setupControlBoard(self):
        btnHt = 5
        col = 0

        ##############ISO##############
        
        self.isoList=[]
        tkinter.Label(self.leftControlFrame,text="ISO").grid(row=0,column=col)
        col +=1
        # for i in range(len(self.isoNumbers)):
        #     radioBtn=tkinter.Radiobutton(self.leftControlFrame,padx=0,bg="pink",height=btnHt,text=self.isoNumbers[i],command=self.onIsoSelected,variable=self.iso_number, value=self.isoNumbers[i])
        #     radioBtn.grid(row=0,column=col)
        #     self.isoList.append(radioBtn)
        #     col += 1

        isoMenu = tkinter.Entry(self.leftControlFrame, textvariable=self.iso_number)
        isoMenu.grid(row=0, column=col)
        self.isoList.append(isoMenu)
        col +=1 
        
        ##############EXPOSIURE TIME##############
        
        self.expList=[]
        tkinter.Label(self.leftControlFrame,text="EXPOSURE").grid(row=0,column=col)
        col += 1
        # for i in range(len(self.expTimes)):
        #     radioforexp=tkinter.Radiobutton(self.leftControlFrame,padx=0,bg="pink",height=btnHt,text=self.expTimes[i],command=self.onExpSelected,variable=self.exp_time, value=self.expTimes[i])
        #     radioforexp.grid(row=0,column=col)
        #     self.expList.append(radioforexp)
        #     col += 1

        expMenu = tkinter.Entry(self.leftControlFrame, textvariable=self.exp_time)
        expMenu.grid(row=0, column=col)
        self.expList.append(expMenu)
        col += 1

        ##############EXPOSIURE NUMBER##############
        tkinter.Label(self.leftControlFrame,text=" ").grid(row=0,column=col)
        col += 1
        tkinter.Button(self.leftControlFrame,text="|\n|\nV",command=self.exp_number_down, width=10, height=3).grid(row=0,column=col)
        col += 1
        tkinter.Label(self.leftControlFrame,textvariable=self.exposure_number).grid(row=0,column=col)
        col += 1
        tkinter.Button(self.leftControlFrame,text="^\n|\n|",command=self.exp_number_up, width=10, height=3).grid(row=0,column=col)
        col += 1

        ##### ZOOM ####
        tkinter.Button(self.leftControlFrame, text="Zoom+", command=self.zoomin, width=10, height=3).grid(row=0,column=col)
        col += 1
        tkinter.Button(self.leftControlFrame, text="Zoom-", command=self.zoomout, width=10, height=3).grid(row=0,column=col)
        col += 1

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
        def coolproc():
            self.camera.coolto(0)

        thread = Thread(target=coolproc)
        thread.start()
        while thread.is_alive():
            self.cameraTemp = f"Cooling, {self.camera.temperature}C"
            time.sleep(3)
        self.cameraTemp = f"Done cooling: {self.camera.temperature}C"
    
    def warmCamera(self):
        def warmproc():
            self.camera.warmto(0)

        thread = Thread(target=warmproc)
        thread.start()
        while thread.is_alive():
            self.cameraTemp = f"Warming, {self.camera.temperature}C"
            time.sleep(3)
        self.cameraTemp = f"Done warming: {self.camera.temperature}C"

    def updateInfo(self):
        self.cameraTemp = f"Temp: {self.camera.temperature}C"
        self.focuserPos = f"Pos: {self.focuser.position}"

    def setupTestStart(self):
        
        row = 0
        col = 0

        tkinter.Button(self.rightControlFrame, text="Cool", command=self.coolCamera).grid(row=row,column=col,padx=5, pady=5)
        col += 1
        tkinter.Label(self.rightControlFrame, textvariable=self.cameraTemp).grid(row=row,column=col,padx=5, pady=5)
        col += 1
        tkinter.Button(self.rightControlFrame, text="Warm", command=self.warmCamera).grid(row=row,column=col,padx=5, pady=5)

        row += 1
        col = 0
        tkinter.Label(self.rightControlFrame,textvariable=self.focuserPos).grid(row=row,column=col,padx=5, pady=5)

        row += 1
        col = 0

        tkinter.Label(self.rightControlFrame,textvariable=self.expVar).grid(row=row,column=col,padx=5, pady=5)
        
        row += 1
        col = 0

        col += 1
        self.snapshotBtn = tkinter.Button(self.rightControlFrame,text="SNAPSHOT",command=self.takeSnapshot, width=10, height=3)
        self.snapshotBtn.grid(row=row, column=col,padx=5, pady=5)

        row += 1
        col = 0

        tkinter.Button(self.rightControlFrame,text="Cancel", command=self.cancel, width=10, height=3).grid(row=row,column=col,padx=5, pady=5)

        col += 1
        self.startBtn = tkinter.Button(self.rightControlFrame,text="START",command=self.startExps, width=10, height=3)
        self.startBtn.grid(row=row, column=col,padx=5, pady=5)
        


if __name__ == "__main__":

    ap = ArgumentParser()
    ap.add_argument("cameraModel", type=int, choices=[90, 750, 5300, 294])
    args = ap.parse_args()

    destDir = ".\images"
    Path(destDir).mkdir(exist_ok=True)

    astroCam = AstroCam(str(args.cameraModel), destDir)
    astroCam.setupControlBoard()
    astroCam.setupTestStart()
    astroCam.root.mainloop()
