from service_base import ServiceBase
import tkinter as tk
import time
from datetime import datetime
from astropy.io import fits
from image_data import ImageData


class CaptureService(ServiceBase):

    CaptureStatusUpdateEventName = "<<CaptureStatusUpdate>>"

    def __init__(self, tk_root, camera):
        super().__init__(tk_root)
        self._camera = camera
        self._image_count = 0

    def process(self):
        if self._camera is not None and self._camera.connected:
            self._camera.gain = self.job['iso']
            self._camera.start_exposure(self.job['exp'])
            self.job['date_obs'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
            img_dt = 500 # ms
            img_steps = int(self.job['exp'] * 1000 / img_dt)
            steps = 0
            while not self._camera.imageready:
                time.sleep(img_dt / 1000)
                steps += 1
                self._tk_root.event_generate(self.CaptureStatusUpdateEventName, when="tail", x=1, y=int(100*steps/img_steps))

            img = self._camera.downloadimage()
            temperature = self._camera.temperature
            hdr = fits.Header({
                'COMMENT': 'Anand Dinakar',
                'OBJECT': self.job["object_name"],
                'INSTRUME': self._camera.name,
                'DATE-OBS': self.job['date_obs'],
                'EXPTIME': self.job['exp'],
                'CCD-TEMP': temperature,
                'XPIXSZ': self._camera.pixelSize[0], #4.63,
                'YPIXSZ': self._camera.pixelSize[1], #4.63,
                'XBINNING': self._camera.binning,
                'YBINNING': self._camera.binning,
                'XORGSUBF': 0,
                'YORGSUBF': 0,
                'BZERO': 0,
                'BSCALE': 1,
                'EGAIN': self._camera.egain,
                'FOCALLEN': self.job["focal_length"],
                'SWCREATE': 'AstroCAM',
                'SBSTDVER': 'SBFITSEXT Version 1.0',
                'SNAPSHOT': 1,
                'SET-TEMP': self._camera.set_temp,
                'IMAGETYP': self.job['image_type'], #'Light Frame',
                'SITELAT': self.job["latitude"],
                'SITELONG': self.job["longitude"],
                'GAIN': self.job['iso'],
                'OFFSET': self._camera.offset,
                'BAYERPAT': self._camera.sensor_type.name
            })
            if 'output_fname' in self.job:
                output_fname = self.job['output_fname']
                hdu = fits.PrimaryHDU(img, header=hdr)
                hdu.writeto(output_fname)
            else:
                output_fname = None
            self.output = ImageData(img, output_fname, hdr)
            self._image_count += 1
            self._tk_root.event_generate(self.CaptureStatusUpdateEventName, when="tail", x=1, y=100)
        else:
            raise RuntimeError("Camera not connected")

    def capture_image(self, job, on_success=None, on_failure=None):
        return self.start_job(job, on_success, on_failure)
    

def main():
    from simulated_devices.simulated_camera import SimulatedCamera

    root = tk.Tk()
    capture_svc = CaptureService(root, camera=SimulatedCamera(r"C:\code\astrocam\images\20250821\M13\Light"))
    capture_svc.subscribe(lambda img: print("Image data callback received:", img))

    def process_status_update(e):
        print("Capture status update:", e.x, e.y)

    root.bind(capture_svc.CaptureStatusUpdateEventName, process_status_update)

    def process_image(job, img):
        status_var.set("Image captured: {}".format(img))

    def start_capture():
        job = {
            "object_name": "bakundi",
            "focal_length": 100,
            "latitude": 0,
            "longitude": 0,
            "iso": 200,
            "exp": 4,
            "image_type": "Light",
            "output_fname": "test.fit"
        }
        capture_svc.capture_image(job, on_success=process_image, on_failure=lambda job, err: status_var.set(f"Capture failed: {err}"))

    btn = tk.Button(root, text="Capture", command=start_capture)
    btn.pack()
    status_var = tk.StringVar(value="Ready")
    status_label = tk.Label(root, textvariable=status_var)
    status_label.pack()

    root.mainloop()

    capture_svc.terminate()

if __name__ == "__main__":
    main()
