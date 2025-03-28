import random
import traceback
import tkinter as tk
import tkinter.ttk as ttk

from datetime import datetime, timedelta
import time
from pathlib import Path

import subprocess
from image_data import ImageData
from snap_process import ProgressData

from multiprocessing import Queue
import queue

from app import AstroApp
from ui.focuser_widget import FocuserWidget
from ui.fwhm_widget import FWHMWidget
from ui.histogram_plot import HistogramViewer
from ui.image_container import ImageViewer
from ui.equipment_selector import selectEquipment
from ui.mount_status_widget import MountStatusWidget

from astropy.io import fits


DEFAULT_NUM_EXPS = 5

class AstroCam(AstroApp):
    def __init__(self, destDir):
        super().__init__()
        self.mount = None
        self.camera = None
        self.focuser = None

        self.windowWidth = self.root.winfo_screenwidth()               
        self.windowHeight = self.root.winfo_screenheight()
        self.root.geometry(f"{self.windowWidth}x{self.windowHeight}")
        
        self.root.state("zoomed")

        self.connected = False
        self.destDir = destDir
        self.runningExposures = 0
        self.runningLiveView = False
        self.runningSimulator = False
        self.cancelJob = False
        self.image_queue = Queue(1000)  
        self.req_queue = Queue(1000)
        self.pollingCounter = 0
        self.onImageReady = [] # functions to call on image ready

        ##############VARIABLES##############
        self.runStatus = tk.StringVar()

        self.iso_number=tk.IntVar()
        self.iso_number.set(120)
        self.exp_time=tk.DoubleVar()
        self.exp_time.set(1.0)
        self.exposure_number=tk.IntVar()
        self.exposure_number.set(DEFAULT_NUM_EXPS)
        self.image_type = tk.StringVar()
        self.image_type.set("Light")

        self.obsObject = tk.StringVar()
        self.obsObject.set("Unknown")
        self.focalLength = tk.IntVar()
        self.focalLength.set(0)
        self.latitude = tk.StringVar()
        self.latitude.set("+40 51 55.000")
        self.longitude = tk.StringVar()
        self.longitude.set("-74 20 42.000")

        # Layout
        paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)

        # Image container
        imageViewerFrame = ttk.Frame(paned_window)
        imageViewerFrame.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)
        self.imageViewer = ImageViewer(imageViewerFrame)

        # Control panel on right
        scrollableControlPanelFrame, controlPanelFrame = self.createScollableControlPanel(paned_window)

        # Add the frames to the PanedWindow
        paned_window.add(imageViewerFrame, weight=99)
        paned_window.add(controlPanelFrame, weight=1)

        # Histogram
        histoFrame=tk.Frame(scrollableControlPanelFrame, bg='black')
        self.histoViewer = HistogramViewer(histoFrame, image_container=self.imageViewer)
        histoFrame.pack(fill=tk.X, side=tk.TOP, pady=3)

        # On / Off Button
        self.on_icon = tk.PhotoImage(file='icons/on.png')
        self.off_icon = tk.PhotoImage(file='icons/off.png')
        self.connectBtn = ttk.Button(scrollableControlPanelFrame, image=self.on_icon, command=self.toggleconnect)
        self.connectBtn.place(rely=0.0, relx=1.0, x=0, y=0, anchor=tk.NE)

        self.exposureProgress = ttk.Progressbar(scrollableControlPanelFrame, orient='horizontal', mode='determinate', length=100)
        self.exposureProgress.pack(fill=tk.X, side=tk.TOP, pady=0)

        # Status message
        ttk.Label(scrollableControlPanelFrame, textvariable=self.runStatus).pack(fill=tk.X, side=tk.TOP, pady=5)

        # Focuser and thermal controls
        widgetsFrame = ttk.Frame(scrollableControlPanelFrame, relief='raised')

        # Focuser controls
        focusFrame = ttk.Frame(widgetsFrame)
        self.focuserWidget = FocuserWidget(focusFrame, self, self.focuser)
        self.root.bind("<Key>", self.focuserWidget.onkeypress)
        focusFrame.pack(fill=tk.X, side=tk.TOP)

        # Setup mount status
        mountStatusFrame = ttk.Frame(widgetsFrame)
        self.mountStatusWidget = MountStatusWidget(mountStatusFrame, self, self.mount)
        mountStatusFrame.pack(fill=tk.X, side=tk.TOP)

        # Star stats
        starStatFrame = ttk.Frame(widgetsFrame)
        self.fwhmWidget = FWHMWidget(widgetsFrame)
        starStatFrame.pack(fill=tk.BOTH, side=tk.TOP)
        self.imageViewer.onTargetStarChanged = lambda star: self.fwhmWidget.setTargetStar(star)

        widgetsFrame.pack(fill=tk.BOTH, side=tk.TOP)

        # Imaging controls
        imagingControlsFrame=ttk.Frame(scrollableControlPanelFrame, relief='raised')
        self.setupControlBoard(imagingControlsFrame)
        imagingControlsFrame.pack(fill=tk.BOTH, side=tk.BOTTOM)

        self.enableExpButtons(False)
        self.root.after(1000, self.loadSplashImage)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if tk.messagebox.askokcancel("Quit", "Are you sure you want to exit?"):
            if self.runningExposures or self.runningLiveView:
                self.cancel()
            self.root.destroy()


    def loadSplashImage(self):
        # img_root = Path(r"C:\images\plate-solving-samples")
        # img_dir = random.choice([d for d in img_root.iterdir() if d.is_dir()])
        # image_fname = str(random.choice(list(img_dir.glob("**/*.fit"))))
        image_fname = r"splash.fit"
        imageData = ImageData(raw=None, fname=image_fname, header=None)
        self.histoViewer.update(imageData)
        self.imageViewer.update(imageData)
        imageData.computeStars()
        if self.fwhmWidget.update(imageData):
            if self.onImageReady:
                fn = self.onImageReady.pop()
                fn(imageData)
            self.imageViewer.updateStars()


    def createScollableControlPanel(self, parentFrame, width=350):
        controlPanelFrame = ttk.Frame(parentFrame, width=width)
        controlPanelFrame.pack(fill=tk.Y, side=tk.RIGHT)
        # Create a canvas to hold the content of controlPanelFrame
        canvas = tk.Canvas(controlPanelFrame, background="#200", width=width)
        # Create a frame inside the canvas for the content of controlPanelFrame
        scrollableControlPanelFrame = ttk.Frame(canvas, width=width)
        # Create a vertical scrollbar
        scrollbar = ttk.Scrollbar(controlPanelFrame, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas.create_window((0, 0), window=scrollableControlPanelFrame, anchor=tk.NW)
        scrollableControlPanelFrame.bind("<Configure>", lambda evt: canvas.configure(scrollregion=canvas.bbox("all")))
        return scrollableControlPanelFrame, controlPanelFrame

    def setupControlBoard(self, frame):
        settingsFrame = ttk.Frame(frame)
        # Observation target
        observationFrame = ttk.Frame(settingsFrame)
        ttk.Label(observationFrame, text="Observation ").grid(row=0, column=0, padx=5)
        ttk.Button(observationFrame, textvariable=self.obsObject, command=self.obs_popup).grid(row=0, column=1, padx=5)
        observationFrame.pack(fill=tk.X, side=tk.TOP, pady=5)

        # Basic imaging controls
        settingsRow1 = ttk.Frame(settingsFrame)

        # Image type
        imagetTypeFrame = ttk.Frame(settingsRow1)
        ttk.Label(imagetTypeFrame, text="Type").pack(side=tk.LEFT)
        ttk.Combobox(imagetTypeFrame,
                     textvariable=self.image_type,
                     values=["Light", "Dark", "Flat", "Bias"],
                     state='readonly', width=5, font=self.EntryFont).pack(side=tk.LEFT)
        imagetTypeFrame.pack(side=tk.LEFT, pady=3)

        # Gain / ISO
        isoFrame = ttk.Frame(settingsRow1)
        ttk.Label(isoFrame,text="ISO").pack(side=tk.LEFT)
        self.isoField = ttk.Entry(isoFrame, textvariable=self.iso_number, font=self.EntryFont, width=self.entryWidth)
        self.isoField.pack(side=tk.LEFT)
        isoFrame.pack(side=tk.LEFT, pady=3)

        # Shutter / Exposure length
        shutterFrame = ttk.Frame(settingsRow1)
        ttk.Label(shutterFrame,text="Shutter").pack(side=tk.LEFT)
        self.shutterField = ttk.Entry(shutterFrame, textvariable=self.exp_time, font=self.EntryFont, width=self.entryWidth)
        self.shutterField.pack(side=tk.LEFT)
        shutterFrame.pack(side=tk.RIGHT, pady=3)
        settingsRow1.pack(fill=tk.X, side=tk.TOP)

        # Number of images / subs
        expFrame = ttk.Frame(settingsFrame)
        ttk.Label(expFrame, text="Subs: ").pack(side=tk.LEFT)
        ttk.Button(expFrame,text="\u2193",command=self.exp_number_down, style='X.TButton', width=2).pack(side=tk.LEFT)
        self.numFramesField = ttk.Entry(expFrame,textvariable=self.exposure_number, font=self.EntryFont, width=self.entryWidth)
        self.numFramesField.pack(side=tk.LEFT)
        ttk.Button(expFrame,text="\u2191",command=self.exp_number_up, style='X.TButton', width=2).pack(side=tk.LEFT)
        expFrame.pack(fill=tk.X, side=tk.TOP, pady=3)

        settingsFrame.pack(fill=tk.X, side=tk.TOP, padx=5, pady=5)

        # Main buttons to start sequences
        controlFrame = ttk.Frame(frame)
        self.liveviewBtn = ttk.Button(controlFrame,text="LiveView",command=self.startLiveview)
        self.liveviewBtn.grid(row=0, column=0, padx=2, pady=2)
        self.snapshotBtn = ttk.Button(controlFrame,text="Snap",command=self.takeSnapshot)
        self.snapshotBtn.grid(row=0, column=1, padx=2, pady=2)
        self.startBtn = ttk.Button(controlFrame,text="Start",command=self.startExps)
        self.startBtn.grid(row=0, column=2, padx=2, pady=2)
        ttk.Button(controlFrame,text="Stop", command=self.cancel).grid(row=1, column=2, padx=2, pady=2)
        controlFrame.pack(fill=tk.X, side=tk.TOP, padx=5, pady=5)

    # Observation settings
    def obs_popup(self):
        win = tk.Toplevel()
        win.wm_title("Window")

        mainframe = ttk.Frame(win)
        row = 0
        ttk.Label(mainframe, text="Object Name").grid(row=row, column=0, padx=2, pady=2)
        ttk.Entry(mainframe, textvariable=self.obsObject).grid(row=row, column=1, padx=2, pady=2)
        row+=1

        ttk.Label(mainframe, text="Focal Length").grid(row=row, column=0)
        ttk.Entry(mainframe, textvariable=self.focalLength).grid(row=row, column=1, padx=2, pady=2)
        row+=1

        ttk.Label(mainframe, text="Latitude").grid(row=row, column=0)
        ttk.Entry(mainframe, textvariable=self.latitude).grid(row=row, column=1, padx=2, pady=2)
        row+=1

        ttk.Label(mainframe, text="Longitude").grid(row=row, column=0, padx=2, pady=2)
        ttk.Entry(mainframe, textvariable=self.longitude).grid(row=row, column=1, padx=2, pady=2)
        row+=1

        ttk.Button(mainframe, text="OK", command=win.destroy).grid(row=row, column=1, padx=2, pady=2)
        mainframe.pack(fill=tk.BOTH, expand=True)

    ##############  Exposures   ###############

    def getExposureSettings(self):
        return {
            "object_name": self.obsObject.get(),
            "focal_length": self.focalLength.get(),
            "latitude": self.latitude.get(),
            "longitude": self.longitude.get(),
            "iso": self.iso_number.get(),
            "exp": self.exp_time.get(),
            "image_type": self.image_type.get(),
        }

    def startExps(self):
        print(f"iso={self.iso_number.get()}, exposiure time={self.exp_time.get()}, and number of exposiures:{self.exposure_number.get()} I am sorry about the horrible spmlxivgz!!!!!! I hopee u engoied.")
        self.runningExposures = 1
        self.runningLiveView = False
        self.cancelJob = False
        self.runStatus.set(f"Started sequence")
        job = self.getExposureSettings()
        self.startNextExposure(job)

    def takeSnapshot(self, iso_override=None, exp_override=None):
        print(f"iso={self.iso_number.get()}, exposiure time={self.exp_time.get()}")
        self.exposure_number.set(1)
        self.runningLiveView = False
        self.runStatus.set(f"Taking snapshot")
        job = self.getExposureSettings()
        if iso_override is not None:
            job['iso'] = iso_override
        if exp_override is not None:
            job['exp'] = exp_override
        self.startNextExposure(job)

    def startLiveview(self):
        print(f"iso={self.iso_number.get()}, exposiure time={self.exp_time.get()}")
        self.cancelJob = False
        self.runningLiveView = True
        self.enableExpButtons(False)
        self.runStatus.set("Live view")
        self.clearInputQueue()

        job = self.getExposureSettings()
        self.startNextExposure(job)

    def startNextExposure(self, job):
        if self.camera is not None and self.camera.connected:
            self.camera.gain = job['iso']
            self.camera.start_exposure(job['exp'])
            job['date_obs'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            time_ms = int(job['exp'] * 1000)
            if time_ms >= 1000:
                self.root.after(1000, self.incrementProgress, job, time_ms)
            else:
                self.root.after(time_ms, self.endExposure, job)

    def incrementProgress(self, job, time_left_ms):
        total_time_ms = int(job['exp'] * 1000)
        time_completed_ms = total_time_ms - time_left_ms
        self.updateProgress(ProgressData(time_completed_ms / total_time_ms))
        time_left_ms -= 1000
        if time_left_ms >= 1000:
            self.root.after(1000, self.incrementProgress, job, time_left_ms)
        else:
            self.root.after(time_left_ms, self.endExposure, job)

    def endExposure(self, job):
        self.updateProgress(ProgressData(1.0))
        if self.camera is None or not self.camera.connected:
            # Failed to download image 
            # Catastrophe!!
            print("Camera not connected!")
            self.endRunningExposures("Camera not connected!")
            return

        if not self.camera.imageready:
            self.root.after(250, self.endExposure, job)
            return
        img = self.camera.downloadimage()
        temperature = self.camera.temperature

        hdr = fits.Header({
            'COMMENT': 'Anand Dinakar',
            'OBJECT': job["object_name"],
            'INSTRUME': self.camera.name,
            'DATE-OBS': job['date_obs'],
            'EXPTIME': job['exp'],
            'CCD-TEMP': temperature,
            'XPIXSZ': self.camera.pixelSize[0], #4.63,
            'YPIXSZ': self.camera.pixelSize[1], #4.63,
            'XBINNING': self.camera.binning,
            'YBINNING': self.camera.binning,
            'XORGSUBF': 0,
            'YORGSUBF': 0,
            'BZERO': 0,
            'BSCALE': 1,
            'EGAIN': self.camera.egain,
            'FOCALLEN': job["focal_length"],
            'SWCREATE': 'AstroCAM',
            'SBSTDVER': 'SBFITSEXT Version 1.0',
            'SNAPSHOT': 1,
            'SET-TEMP': self.camera.set_temp,
            'IMAGETYP': job['image_type'], #'Light Frame',
            'SITELAT': job["latitude"],
            'SITELONG': job["longitude"],
            'GAIN': job['iso'],
            'OFFSET': self.camera.offset,
            'BAYERPAT': self.camera.sensor_type.name
        })

        if not self.runningLiveView and not self.runningSimulator:
            sno_file = Path('serial_no.txt')
            if sno_file.exists():
                serial_no = int(sno_file.read_text())
            else:
                serial_no = 0
            sno_file.write_text(str(serial_no+1))

            now = datetime.now()
            now = now - timedelta(days=1 if now.hour<6 else 0)
            output_dir = self.destDir / now.strftime("%Y%m%d")
            if job['image_type'] == 'Light':
                output_dir = output_dir / f"{job['object_name']}/Light"
            else:
                output_dir = output_dir / f"{job['image_type']}_{job['exp']}sec_{job['iso']}gain"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_fname = output_dir / f"{job['image_type']}_{serial_no:05d}_{job['exp']}sec_{job['iso']}gain_{temperature}C.fit"
            hdu = fits.PrimaryHDU(img, header=hdr)
            hdu.writeto(output_fname)
        else:
            output_fname = None

        # Start next exposure
        self._start_next_exposure(job)

        # Process last image & update UI
        imageData = ImageData(img, output_fname, hdr)
        self.histoViewer.update(imageData)
        self.imageViewer.update(imageData)
        
        if job['image_type'] == 'Light' and not self.runningLiveView:
            imageData.computeStars()
            if self.fwhmWidget.update(imageData):
                if self.onImageReady:
                    fn = self.onImageReady.pop()
                    fn(imageData)
                self.imageViewer.updateStars()

    def _start_next_exposure(self, job):
        # Start next exposure
        if self.runningLiveView:
            if self.cancelJob:
                self.endRunningExposures("Stopped Live view")
            else:
                self.startNextExposure(job)
                return
        elif self.runningExposures:
            if self.cancelJob:
                self.endRunningExposures("Cancelled")
                return
            else:
                self.exposure_number.set(self.exposure_number.get() - 1)
            if self.exposure_number.get() == 0:
                self.endRunningExposures("Finished")
                return
            else:
                # Execute after exposure steps
                
                # Trigger next exposure
                self.startNextExposure(job)
        else:
            self.endRunningExposures("Finished")
            return

    def endRunningExposures(self, msg):
        self.runningExposures = 0
        self.exposure_number.set(DEFAULT_NUM_EXPS)
        self.runStatus.set(msg)
        self.enableExpButtons(True)
        self.updateProgress()


    def clearInputQueue(self):
        # Clear request queue
        try:
            while not self.req_queue.empty():
                self.req_queue.get_nowait()
        except queue.Empty:
            pass

    def enableExpButtons(self, enable=True):
        newstate = "normal" if enable else "disabled"
        self.startBtn["state"] = newstate
        self.snapshotBtn["state"] = newstate
        self.liveviewBtn["state"] = newstate
        self.shutterField["state"] = newstate
        self.isoField["state"] = newstate
        self.numFramesField["state"] = newstate

    def updateProgress(self, progressData=None):
        if progressData is None:
            self.exposureProgress['value'] = 0
        else:
            self.exposureProgress['value'] = int(progressData.progress*100)

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
            exp_job = self.getExposureSettings()
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
                    self.req_queue.get_nowait()
            except queue.Empty:
                pass


    ##################### Event Handlers #######################

    def statusPolling(self):
        if self.connected:
            arr = [self.mountStatusWidget, self.focuserWidget]
            arr[self.pollingCounter % len(arr)].update()
            self.pollingCounter += 1
            self.root.after(1000, self.statusPolling)

    def toggleconnect(self):
        if self.connected:
            if tk.messagebox.askokcancel("Disconnect", "Are you sure you want to disconnect?") is False:
                return
            if self.runningExposures or self.runningLiveView:
                self.cancel()

            self.connectBtn['image'] = self.on_icon
            self.connected = False
            if self.mount:
                self.mount.close()
            if self.camera:
               self.camera.close()
            if self.focuser:
                self.focuser.close()
            self.mount = None
            self.camera = None
            self.focuser = None
            self.mountStatusWidget.disconnect()
            self.focuserWidget.disconnect()
            self.runStatus.set("Disconnected")
            self.enableExpButtons(False)
        else:
            try:
                self.mount, self.camera, self.focuser = selectEquipment(self.root)
                if self.mount is None or self.camera is None or self.focuser is None:
                    return
                subprocess.Popen(["python.exe", "./coolerapp.py", self.camera.name], creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP, close_fds=True)
                self.runningSimulator = self.camera.isSimulator()
                self.mountStatusWidget.connect(self.mount)
                self.focuserWidget.connect(self.focuser)
                self.connected = True
                self.connectBtn['image'] = self.off_icon
                self.root.after_idle(self.statusPolling)
                self.runStatus.set("Connected")
                self.enableExpButtons(True)
            except Exception as err:
                traceback.print_exc()
                self.runStatus.set("Unable to connect")
                return

    @staticmethod
    def run():
        destDir = Path(".\images")
        destDir.mkdir(exist_ok=True)
        astroCam = AstroCam(destDir)
        astroCam.root.mainloop()

if __name__ == "__main__":
    AstroCam.run()
