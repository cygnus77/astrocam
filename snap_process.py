from pathlib import Path
from Alpaca.camera import Camera
from Alpaca.focuser import Focuser
from multiprocessing import Process, Queue
import queue
from threading import Thread
import itertools
import time
import shutil
import tempfile
from datetime import datetime
from astropy.io import fits
import os

class ImageData:
    def __init__(self, image, fname, header):
        self._image = image
        self._fname = fname
        self._header = header

    @property
    def image(self):
        return self._image
    @property
    def fname(self):
        return self._fname
    @property
    def header(self):
        return self._header
    
    def close(self):
       self._image = None
       self._fname = None
       self._header = None


class ProgressData:
    def __init__(self, progress):
        self._progress = progress    
    @property
    def progress(self):
        return self._progress


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
            flist = itertools.cycle(Path(r"images").glob("*.fit"))
            while True:
                exp_job = self.input_queue.get(block=self.liveview)
                if not exp_job:
                    break
                if exp_job['exp'] > 1:
                    for j in range(int(exp_job['exp'])):
                        time.sleep(1)
                        self.output_queue.put(ProgressData(j / exp_job['exp']))
                else:
                    time.sleep(exp_job['exp'])
                fname = next(flist)

                f = fits.open(fname)
                ph = f[0]
                img = ph.data

                if 'liveview' in exp_job:
                    # output_fname = tempfile.gettempdir() + f"/liveview_{datetime.now().timestamp()}.fit"
                    # shutil.copy(fname, output_fname)
                    output_fname = None
                else:
                    output_fname = str(fname)

                self.output_queue.put(ImageData(img, output_fname, ph.header))

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
                if exp_job is None:
                    break
                self.cam.gain = exp_job['iso']
                self.cam.start_exposure(exp_job['exp'])
                date_obs = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                
                if exp_job['exp'] > 1:
                    for j in range(int(exp_job['exp'])):
                        time.sleep(1)
                        self.output_queue.put(ProgressData(j / exp_job['exp']))
                else:
                    time.sleep(exp_job['exp'])

                while not self.cam.imageready:
                    print('waiting')
                    time.sleep(0.25)

                img = self.cam.downloadimage()
                temperature = self.cam.temperature

                if 'liveview' not in exp_job:
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
                        'IMAGETYP': exp_job['image_type'], #'Light Frame',
                        'SITELAT': exp_job["latitude"],
                        'SITELONG': exp_job["longitude"],
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

                    output_fname = self.destDir / f"{exp_job['image_type']}_{serial_no:05d}_{exp_job['exp']}sec_{exp_job['iso']}gain_{temperature}C.fit"
                    hdu = fits.PrimaryHDU(img, header=hdr)
                    hdu.writeto(output_fname)
                else:
                    output_fname = None

                self.output_queue.put(ImageData(img, output_fname, hdr))

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
