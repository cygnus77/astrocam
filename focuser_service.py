from service_base import ServiceBase
from capture_service import CaptureService
import time
import numpy as np
from datetime import datetime
from astropy.io import fits
from image_data import ImageData


class FocuserService(ServiceBase):

    PositionUpdateEventName = "<<focuser_position_update>>"
    AutofocusEventName = "<<autofocus_event>>"

    def __init__(self, tk_root, focuser, camera_svc):
        super().__init__(tk_root)
        self._focuser = focuser
        self._camera_svc = camera_svc
        self._tk_root.after(1000, self._poll_focuser_position)

    def _publish_focuser_position(self):
        if self._focuser is not None and self._focuser.connected:
            self._tk_root.event_generate(FocuserService.PositionUpdateEventName, when="tail", x=0, y=self._focuser.position)

    def _poll_focuser_position(self):
        self._publish_focuser_position()
        self._tk_root.after(5000, self._poll_focuser_position)

    def process(self):
        if self._focuser is not None and self._focuser.connected:

            if self.job['cmd'] == 'goto':
                self._goto(self.job['position'])

            elif self.job['cmd'] == 'movein':
                self._movein(self.job['steps'])

            elif self.job['cmd'] == 'moveout':
                self._moveout(self.job['steps'])

            elif self.job['cmd'] == 'autofocus':
                self.autofocus_number = f"{np.random.randint(0, 100000):05d}"
                start_minima = minima = self._focuser.position
                search_width = 100
                bounds = (minima - search_width, minima + search_width)

                self._tk_root.event_generate(FocuserService.AutofocusEventName, when="tail", x=0, y=start_minima)

                fwhms = []

                for offset in [-search_width, search_width, -(search_width//2), (search_width//2)]:
                    pos = self._goto(minima + offset)
                    fwhms.append((minima + offset, self._snap(pos)))
    
                # fit curve
                coeffs = np.polyfit([x[0] for x in fwhms], [x[1] for x in fwhms], deg=2)
                if coeffs[0] < 0:
                    # failed
                    raise RuntimeError(f"Fit failed: {coeffs}")

                self._tk_root.event_generate(FocuserService.AutofocusEventName, when="tail", x=1, y=minima)

                # calc new minima
                minima = int(-coeffs[1]/(2*coeffs[0]))
                tgt_fwhm = np.polyval(coeffs, minima)
                if minima < bounds[0]:
                    minima = bounds[0]
                elif minima > bounds[1]:
                    minima = bounds[1]

                pos = self._goto(minima)
                fwhms.append((minima + offset, fwhm := self._snap(pos)))

                sign = 1
                delta = 1
                while fwhm > tgt_fwhm + 1 and delta < search_width:
                    minima += sign * delta
                    delta = delta * 2
                    sign = -sign
                    pos = self._goto(minima)
                    fwhms.append((minima + offset, fwhm := self._snap(pos)))

                if fwhm > tgt_fwhm + 1:
                    min_pos = np.argmin([x[1] for x in fwhms])
                    self._goto(fwhms[min_pos][0])
                    self._tk_root.event_generate(FocuserService.AutofocusEventName, when="tail", x=2, y=fwhms[min_pos][0])
                    return

                self._tk_root.event_generate(FocuserService.AutofocusEventName, when="tail", x=3, y=minima)
                return

        else:
            raise RuntimeError("Focuser not connected")

    def _snap(self, position):
        job = {
            "object_name": "auto_focus",
            "focal_length": 0,
            "latitude": None,
            "longitude": None,
            "iso": 200,
            "exp": 5.0,
            "image_type": "Light",
            "output_fname": f"{self.autofocus_number}_{position}_focus.fit"
        }
        imageData = self._camera_svc.run_job(job)
        if imageData is None:
            raise RuntimeError("Capture failed")
        imageData.computeStars()
        fwhm = np.sqrt(imageData.stars.fwhm_x**2 + imageData.stars.fwhm_y**2).mean()
        return fwhm

    # def _snap(self, position):
    #     exposure_time = 5.0
    #     gain = 200
    #     save_focus_images = True

    #     if self._camera is not None and self._camera.connected:
    #         self._camera.gain = gain
    #         self._camera.start_exposure(exposure_time)
    #         img_dt = 500 # ms
    #         img_steps = int(exposure_time * 1000 / img_dt)
    #         steps = 0
    #         while not self._camera.imageready:
    #             time.sleep(img_dt / 1000)
    #             steps += 1
    #             self._tk_root.event_generate(CaptureService.CaptureStatusUpdateEventName, when="tail", x=1, y=int(100*steps/img_steps))
    #         img = self._camera.downloadimage()
    #         temperature = self._camera.temperature
    #         hdr = fits.Header({
    #             'COMMENT': 'Anand Dinakar',
    #             'OBJECT': "auto_focus",
    #             'INSTRUME': self._camera.name,
    #             'DATE-OBS': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
    #             'EXPTIME': exposure_time,
    #             'CCD-TEMP': temperature,
    #             'XPIXSZ': self._camera.pixelSize[0], #4.63,
    #             'YPIXSZ': self._camera.pixelSize[1], #4.63,
    #             'XBINNING': self._camera.binning,
    #             'YBINNING': self._camera.binning,
    #             'XORGSUBF': 0,
    #             'YORGSUBF': 0,
    #             'BZERO': 0,
    #             'BSCALE': 1,
    #             'EGAIN': self._camera.egain,
    #             'SWCREATE': 'AstroCAM',
    #             'SBSTDVER': 'SBFITSEXT Version 1.0',
    #             'SNAPSHOT': 1,
    #             'SET-TEMP': self._camera.set_temp,
    #             'IMAGETYP': 'Light Frame',
    #             'GAIN': gain,
    #             'OFFSET': self._camera.offset,
    #             'BAYERPAT': self._camera.sensor_type.name
    #         })
    #         if save_focus_images:
    #             output_fname = f"{self.autofocus_number}_{position}_focus.fit"
    #             hdu = fits.PrimaryHDU(img, header=hdr)
    #             hdu.writeto(output_fname)
    #         else:
    #             output_fname = None
    #         imageData = ImageData(img, output_fname, hdr)
    #         imageData.computeStars()
    #         fwhm = np.sqrt(imageData.stars.fwhm_x**2 + imageData.stars.fwhm_y**2).mean()
    #         return fwhm

    def _goto(self, position):
        if self._focuser is None or not self._focuser.connected:
            raise RuntimeError("Focuser not connected")
        retry = 3
        while (curr_position:=self._focuser.position) != position and retry > 0:
            self._focuser.goto(position)
            retry -= 1
            time.sleep(0.1)
            self._publish_focuser_position()
        return curr_position

    def _movein(self, steps):
        if self._focuser is None or not self._focuser.connected:
            raise RuntimeError("Focuser not connected")
        self._focuser.movein(steps)
        self._publish_focuser_position()

    def _moveout(self, steps):
        if self._focuser is None or not self._focuser.connected:
            raise RuntimeError("Focuser not connected")
        self._focuser.moveout(steps)
        self._publish_focuser_position()

    def goto(self, position, on_failure=None):
        return self.start_job({'cmd': 'goto', 'position': position}, on_failure=on_failure)

    def movein(self, steps, on_failure=None):
        return self.start_job({'cmd': 'movein', 'steps': steps}, on_failure=on_failure)

    def moveout(self, steps, on_failure=None):
        return self.start_job({'cmd': 'moveout', 'steps': steps}, on_failure=on_failure)

    def autofocus(self, on_success=None, on_failure=None):
        return self.start_job({'cmd': 'autofocus'}, on_success=on_success, on_failure=on_failure)
