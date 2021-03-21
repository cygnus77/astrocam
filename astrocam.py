import sys
import tkinter
import rawpy
from PIL import Image, ImageTk
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, Future

from argparse import ArgumentParser

from CameraAPI.CameraAPI import Camera

DEFAULT_NUM_EXPS = 5

def loadImageHisto(imageFilename, imgCanvasWidth, imgCanvasHeight, histoWidth, histoHeight):
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
    r, g, b = img.split()

    if img.width > img.height:
        w = imgCanvasWidth
        h = int((imgCanvasWidth / img.width) * img.height)
    else:
        h = imgCanvasHeight
        w = int((imgCanvasHeight / img.height) * img.width)
    img = img.resize((w,h))

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
    def __init__(self, windowWidth, windowHeight, snapFn, threadExecutor, processExecutor):
        self.root = tkinter.Tk()
        self.root.geometry(f"{windowWidth+20}x{windowHeight+20}")
        self.snapFn = snapFn
        self.textVar=tkinter.StringVar()
        self.runningExposures = 0
        self.cancelJob = False
        self.imageFilename = None
        self.threadExecutor = threadExecutor
        self.processExecutor = processExecutor


        self.isoNumbers=["640","800","1600","2000","2500","3200","5000","6400","8000", "12800"]
        self.expTimes=[1./256, 1./128,1./64,1./32,1./16,0.125,0.25,0.5,1, 5,10,30,60,90,120,150,180,240,300]

        ##############VARIABLES##############
        self.iso_number=tkinter.StringVar()
        self.iso_number.set(self.isoNumbers[0])
        self.exp_time=tkinter.DoubleVar()
        self.exp_time.set(self.expTimes[0])

        self.exposure_number=tkinter.IntVar()
        self.exposure_number.set(DEFAULT_NUM_EXPS)
        self.parentFrame=tkinter.Frame(self.root)

        col0w = round(0.80 * windowWidth)
        col1w = windowWidth - col0w
        row0h = round(0.10 * windowHeight)
        row1h = round(0.10 * windowHeight)
        row2h = windowHeight - (row0h+row1h)

        self.leftControlFrame=tkinter.Frame(self.parentFrame,height =row0h,width = col0w)
        self.leftControlFrame.grid(row=0,column=0,sticky=tkinter.W)

        self.histoCanvas=tkinter.Canvas(self.parentFrame,height=row0h+row1h, width=col1w, borderwidth=0, highlightthickness=0)
        self.histoCanvas.grid(row=0,column=1,rowspan=2, sticky=tkinter.N)

        self.imageCanvas = tkinter.Canvas(self.parentFrame, height=row1h+row2h, width=col0w, borderwidth=0, highlightthickness=0)
        self.imageCanvas.grid(row=1,column=0,rowspan=2,sticky=tkinter.W)

        self.rightControlFrame=tkinter.Frame(self.parentFrame,height=row2h, width=col1w)
        self.rightControlFrame.grid(row=2,column=1,sticky=tkinter.E)

        self.parentFrame.pack(expand=False)


    def startExps(self):
        print(f"iso={self.iso_number.get()}, exposiure time={self.exp_time.get()}, and number of exposiures:{self.exposure_number.get()} I am sorry about the horrible spmlxivgz!!!!!! I hopee u engoied.")
        self.runningExposures = 1
        self.cancelJob = False
        self.startWorker()

    def takeSnapshot(self):
        print(f"iso={self.iso_number.get()}, exposiure time={self.exp_time.get()}")        
        self.startWorker()

    def endRunningExposures(self, msg):
        self.runningExposures = 0
        self.exposure_number.set(DEFAULT_NUM_EXPS)
        self.textVar.set(msg)
        self.startBtn["state"] = "normal" 
        self.snapshotBtn["state"] = "normal"

    def loadingDone(self, params):
        self.textVar.set("Loaded image")
        
        if self.runningExposures:
            if self.cancelJob:
                self.endRunningExposures("Cancelled")
            elif self.exposure_number.get() > 0:
                self.exposure_number.set(self.exposure_number.get() - 1)
                self.startWorker()
            else:
                self.endRunningExposures("Finished")
        else:
            self.endRunningExposures("Finished")

        self.showImageHisto(*params)

    def processLoadImage(self, params):
        print("Started processing worker")
        future = self.processExecutor.submit(loadImageHisto, *params)
        future.add_done_callback(lambda f: self.root.after(100, self.loadingDone, f.result()))
        # Skip image loading  
        #  self.loadingDone(None)

    def startWorker(self):
        self.imageFilename = None
        self.startBtn["state"] = "disabled"
        self.snapshotBtn["state"] = "disabled"
        self.textVar.set("Taking picture" if self.runningExposures == 0 else "Taking sequence")
        imgCanvasWidth, imgCanvasHeight = int(self.imageCanvas["width"]), int(self.imageCanvas["height"])
        histoWidth, histoHeight = int(self.histoCanvas["width"]), int(self.histoCanvas["height"])

        print("Started capture worker")
        self.threadExecutor.submit(lambda iso,exp: self.snapFn(iso,exp), self.iso_number.get(), self.exp_time.get()).add_done_callback(
            lambda f: self.root.after(100, self.processLoadImage, (f.result(), imgCanvasWidth, imgCanvasHeight, histoWidth, histoHeight))
        )

    def cancel(self):
        self.cancelJob = True

    def exp_number_up(self):
        expnum=self.exposure_number.get()
        if expnum < 5:
            self.exposure_number.set(5)
        else:
            self.exposure_number.set(expnum+5)

    def exp_number_down(self):
        expnum=self.exposure_number.get()
        if expnum <= 5:
            self.exposure_number.set(5)
        else:
            self.exposure_number.set(expnum-5)

    def onIsoSelected(self):
        isoStr = str(self.iso_number.get())
        isoIndex= self.isoNumbers.index(isoStr)
        for i in range(len(self.isoList)):
            self.isoList[i]["bg"]="pink"
        self.isoList[isoIndex]["bg"]="red"

    def onExpSelected(self):
        expTime = self.exp_time.get()
        expIndex= self.expTimes.index(expTime)
        for i in range(len(self.expList)):
            self.expList[i]["bg"]="pink"
        self.expList[expIndex]["bg"]="red"

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

        isoMenu = tkinter.OptionMenu(self.leftControlFrame, self.iso_number, *self.isoNumbers)
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

        expMenu = tkinter.OptionMenu(self.leftControlFrame, self.exp_time, *self.expTimes)
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

        self.onIsoSelected()
        self.onExpSelected()

    def showImageHisto(self, img, histoWidth, histoHeight, red_pts, green_pts, blue_pts):
        self.imageObject = ImageTk.PhotoImage(img)
        self.imageCanvas.delete("all")
        self.imageCanvas.create_image((0,0),image=self.imageObject, anchor='nw')

        self.histoCanvas.delete("all")
        self.histoCanvas.create_rectangle( (0, 0, histoWidth, histoHeight), fill="black")
        self.histoCanvas.create_line(red_pts,fill="red")
        self.histoCanvas.create_line(green_pts,fill="lightgreen")
        self.histoCanvas.create_line(blue_pts,fill="white")

    def setupTestStart(self):
        self.startBtn = tkinter.Button(self.rightControlFrame,text="START",command=self.startExps, width=10, height=3)
        self.startBtn.grid(row=1,column=1,padx=5, pady=5)
        self.snapshotBtn = tkinter.Button(self.rightControlFrame,text="SNAPSHOT",comman=self.takeSnapshot, width=10, height=3)
        self.snapshotBtn.grid(row=0,column=1,padx=5, pady=5)
        tkinter.Label(self.rightControlFrame,textvariable=self.textVar).grid(row=0,column=0,padx=5, pady=5)
        tkinter.Button(self.rightControlFrame,text="Cancel", command=self.cancel, width=10, height=3).grid(row=1,column=0,padx=5, pady=5)

if __name__ == "__main__":

    ap = ArgumentParser()
    ap.add_argument("cameraModel", type=int, choices=[750, 5300])
    args = ap.parse_args()

    destDir = "C:\\src\\pics"
    cam = Camera(args.cameraModel, b"C:\\src\\pics")
    def snapFn(iso, exp):
        cam.setISO(iso)
        imgNo = cam.takePicture(exp)
        print(f"Got file: {destDir}\\Image{imgNo:03d}.nef")
        return f"{destDir}\\Image{imgNo:03d}.nef"

    def testSnapFn(iso,exp):
        print(f"Snap: iso-{iso} - {exp} secs")
        # time.sleep(exp)
        return f"{destDir}\\Image045.nef"

    with ProcessPoolExecutor() as processExecutor, ThreadPoolExecutor() as threadExecutor:
        astroCam = AstroCam(int(1920/1.25), int((1080-100)/1.25), snapFn, threadExecutor, processExecutor) #snapFn)
        astroCam.setupControlBoard()
        astroCam.setupTestStart()
        astroCam.root.mainloop()
