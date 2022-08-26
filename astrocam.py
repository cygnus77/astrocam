import os
from pathlib import Path
import tkinter as tk
import tkinter.ttk as ttk

import time
from multiprocessing import Queue
import queue
from threading import Thread
from argparse import ArgumentParser
import numpy as np
from Alpaca.camera import Camera, Focuser
from snap_process import DummySnapProcess, ImageData, ProgressData, SnapProcess
import time
from ui.cooler_widget import CoolerWidget
from ui.focuser_widget import FocuserWidget
from ui.histogram_plot import HistogramViewer
from ui.image_container import ImageViewer

DEFAULT_NUM_EXPS = 5

HIST_WIDTH = 250
HIST_HEIGHT= 200


class AstroCam:
    def __init__(self, cameraModel, destDir, debug=False):
        self.root = tk.Tk()
        self.cameraModel = cameraModel

        if debug:
            self.snapProcess = DummySnapProcess
        else:
            self.snapProcess = SnapProcess

        self.windowWidth = self.root.winfo_screenwidth()               
        self.windowHeight = self.root.winfo_screenheight()
        self.root.geometry(f"{self.windowWidth}x{self.windowHeight}")
        self.root.bind("<Configure>", self.resize)
        self.root.state("zoomed")

        self.connected = False
        self.camera = None
        self.focuser = None
        self.destDir = destDir
        self.runningExposures = 0
        self.runningLiveView = False
        self.cancelJob = False
        self.image_queue = Queue(1000)  
        self.req_queue = Queue(1000)

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

        self.delay_time = tk.DoubleVar()
        self.delay_time.set(0)
        self.focuser_shift = tk.IntVar()
        self.focuser_shift.set(0)

        self.obsObject = tk.StringVar()
        self.obsObject.set("Unknown")
        self.focalLength = tk.IntVar()
        self.focalLength.set(0)
        self.latitude = tk.StringVar()
        self.latitude.set("+40 51 55.000")
        self.longitude = tk.StringVar()
        self.longitude.set("-74 20 42.000")

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

        self.root.style.map("Vertical.TScrollbar",
            background=[("active", bgcolor),("!active", inactivebgcolor),("pressed",highlightedcolor)])
        self.root.style.map("Horizontal.TScrollbar",
            background=[("active", bgcolor),("!active", inactivebgcolor),("pressed",highlightedcolor)])


        # Layout
        parentFrame=ttk.Frame(self.root, relief=tk.RAISED, borderwidth=1)

        # Image container
        imageViewerFrame = ttk.Frame(parentFrame)
        self.imageViewer = ImageViewer(imageViewerFrame)
        imageViewerFrame.pack(fill=tk.BOTH, side=tk.LEFT, expand=True)

        # Control panel on right
        controlPanelFrame = ttk.Frame(parentFrame)

        # On / Off Button
        self.on_icon = tk.PhotoImage(file='icons/on.png')
        self.off_icon = tk.PhotoImage(file='icons/off.png')
        self.connectBtn = ttk.Button(controlPanelFrame, image=self.on_icon, command=self.toggleconnect)
        self.connectBtn.place(rely=0.0, relx=1.0, x=0, y=0, anchor=tk.NE)

        # Histogram
        histoFrame=tk.Frame(controlPanelFrame, width=HIST_WIDTH, height=HIST_HEIGHT, bg='black')
        self.histoViewer = HistogramViewer(histoFrame, HIST_WIDTH, HIST_HEIGHT)
        histoFrame.pack(side=tk.TOP)
        
        self.exposureProgress = ttk.Progressbar(controlPanelFrame, orient='horizontal', mode='determinate', length=100)
        self.exposureProgress.pack(fill=tk.X, side=tk.TOP, pady=0)

        # Status message
        ttk.Label(controlPanelFrame, textvariable=self.runStatus).pack(fill=tk.X, side=tk.TOP, pady=5)

        # Focuser and thermal controls
        rightControlFrame = ttk.Frame(controlPanelFrame, padding=5, relief='raised')
        # Setup cooler controls
        coolerFrame = ttk.Frame(rightControlFrame)
        self.coolerWidget = CoolerWidget(coolerFrame, self.camera)
        coolerFrame.pack(fill=tk.X, side=tk.TOP)

        # Focuser controls
        focusFrame = ttk.Frame(rightControlFrame)
        self.focuserWidget = FocuserWidget(focusFrame, self.focuser)
        self.root.bind("<Key>", self.focuserWidget.onkeypress)
        focusFrame.pack(fill=tk.X, side=tk.TOP)
        rightControlFrame.pack(fill=tk.BOTH, side=tk.TOP)

        # Imaging controls
        leftControlFrame=ttk.Frame(controlPanelFrame, padding=5, relief='raised')
        self.setupControlBoard(leftControlFrame)
        leftControlFrame.pack(fill=tk.BOTH, side=tk.BOTTOM)

        controlPanelFrame.pack(fill=tk.Y, side=tk.RIGHT)
        parentFrame.pack(fill=tk.BOTH, expand=True)


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
        ttk.Combobox(imagetTypeFrame, textvariable=self.image_type, values=["Light", "Dark", "Flat", "Bias"], state='readonly', width=5, font=self.EntryFont).pack(side=tk.LEFT)
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

        # Additional settings
        extrasFrame = ttk.Frame(settingsFrame)
        delayFrame = ttk.Frame(extrasFrame)
        ttk.Label(delayFrame,text="Delay").pack(side=tk.LEFT)
        ttk.Entry(delayFrame, textvariable=self.delay_time, font=self.EntryFont, width=self.entryWidth).pack(side=tk.LEFT)
        delayFrame.pack(fill=tk.X, side=tk.LEFT)
        focusShiftFrame = ttk.Frame(extrasFrame)
        ttk.Label(focusShiftFrame,text="Focus Shift").pack(side=tk.LEFT)
        ttk.Entry(focusShiftFrame, textvariable=self.focuser_shift, font=self.EntryFont, width=self.entryWidth).pack(side=tk.LEFT)
        focusShiftFrame.pack(fill=tk.X, side=tk.RIGHT)
        extrasFrame.pack(fill=tk.X, side=tk.TOP, pady=3)

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

    # Window resize
    def resize(self, event):
        if(event.widget == self.root and
           (self.windowWidth != event.width or self.windowHeight != event.height)):
            print(f'{event.widget=}: {event.height=}, {event.width=}\n')
            self.windowWidth, self.windowHeight = event.width, event.height

            self.imageViewer.onResize()
            self.histoViewer.onResize()

    ##############  Exposures   ###############

    def getExposureSettings(self):
        return {
            "object_name": self.obsObject.get(),
            "focal_length": self.focalLength.get(),
            "latitude": self.latitude.get(),
            "longitude": self.longitude.get(),
            "iso": self.iso_number.get(),
            "exp": self.exp_time.get(),
            'focuser_adj':  self.focuser_shift.get(),
            'frame_delay':  self.delay_time.get(),
            "image_type": self.image_type.get()
        }

    def startExps(self):
        print(f"iso={self.iso_number.get()}, exposiure time={self.exp_time.get()}, and number of exposiures:{self.exposure_number.get()} I am sorry about the horrible spmlxivgz!!!!!! I hopee u engoied.")
        self.runningExposures = 1
        self.cancelJob = False
        self.startWorker()

    def takeSnapshot(self):
        print(f"iso={self.iso_number.get()}, exposiure time={self.exp_time.get()}")
        self.exposure_number.set(1)
        self.startWorker()

    def startLiveview(self):
        print(f"iso={self.iso_number.get()}, exposiure time={self.exp_time.get()}")
        self.cancelJob = False
        self.runningLiveView = True
        self.enableExpButtons(False)
        self.runStatus.set("Live view")
        self.clearInputQueue()
        def threadProc():
            snapProc = self.snapProcess(self.camera, self.focuser, True, self.req_queue, self.image_queue, self.destDir)
            snapProc.start()
            # Add items for each required exposure
            while not self.cancelJob:
                exp_job = self.getExposureSettings()
                exp_job['liveview'] = True
                self.req_queue.put(exp_job)
                # Get filenames from image queue
                imageData = self.image_queue.get(block=True)
                if isinstance(imageData, ProgressData):
                    self.updateProgress(imageData)
                    continue
                # Update UI
                self.loadImageHisto(imageData)
                imageData.close()

            self.req_queue.put(None)
            while self.image_queue.get() is not None:
                pass
        # Spawn thread
        Thread(target=threadProc, args=[]).start()

    def endRunningExposures(self, msg):
        self.runningExposures = 0
        self.exposure_number.set(DEFAULT_NUM_EXPS)
        self.runStatus.set(msg)
        self.enableExpButtons(True)
        self.progressData = None

    def loadImageHisto(self, imgData: ImageData):
        img = self.imageViewer.setImage(imgData)
        self.histoViewer.setImage(img)

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


    def startWorker(self):
        self.enableExpButtons(False)
        self.runStatus.set("Taking picture" if self.runningExposures == 0 else "Taking sequence")
        self.clearInputQueue()

        exp_job = self.getExposureSettings()

        # Add items for each required exposure
        try:
            for _ in range(self.exposure_number.get()):
                self.req_queue.put(exp_job)
            self.req_queue.put(None)
        except queue.Full:
            pass

        def threadProc():
            # Spawn process
            snapProc = self.snapProcess(self.camera, self.focuser, False, self.req_queue, self.image_queue, self.destDir)
            snapProc.start()

            # Get filenames from image queue
            while not self.cancelJob:
                imageData = self.image_queue.get()
                if imageData == None:
                    # Exit if all exposures are done
                    if self.req_queue.empty():
                        break # done
                    else:
                        # Restart child process - it may have crashed
                        while snapProc.is_alive():
                            time.sleep(1)
                        print("Restarting camera proc")
                        snapProc = self.snapProcess(self.camera, self.focuser, False, self.req_queue, self.image_queue, self.destDir)
                        snapProc.start()
                else:
                    if isinstance(imageData, ProgressData):
                        self.updateProgress(imageData)
                        continue
                    # Update UI
                    self.loadImageHisto(imageData)
                    imageData.close()

        # Spawn thread
        Thread(target=threadProc, args=[]).start()

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
                    self.req_queue.get_nowait(1)
            except queue.Empty:
                pass


    ##################### Event Handlers #######################

    def statusPolling(self):
        if self.connected:
            self.coolerWidget.update()
            self.focuserWidget.update()

            self.root.after(5000, self.statusPolling)

    def toggleconnect(self):
        if self.connected:
            self.connectBtn['image'] = self.on_icon
            self.connected = False
            self.camera.close()
            self.focuser.close()
            self.camera = None
            self.focuser = None
        else:
            try:
                self.camera = Camera(self.cameraModel)
                self.focuser = Focuser("focus")
                self.connected = True
                self.connectBtn['image'] = self.off_icon
                self.root.after_idle(self.statusPolling)
            except Exception as err:
                self.runStatus.set("Unable to connect")
                return

if __name__ == "__main__":

    ap = ArgumentParser()
    ap.add_argument("cameraModel", type=int, choices=[90, 750, 5300, 294])
    ap.add_argument("--debug", action='store_true', default=False)
    args = ap.parse_args()

    destDir = ".\images"
    Path(destDir).mkdir(exist_ok=True)

    astroCam = AstroCam(str(args.cameraModel), destDir, debug=args.debug)
    astroCam.root.mainloop()
