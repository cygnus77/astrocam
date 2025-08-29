from service_base import ServiceBase
from capture_service import CaptureService
import time
import numpy as np
from datetime import datetime
from astropy.io import fits
from image_data import ImageData
import logging


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
        try:
            self._publish_focuser_position()
        except Exception as e:
            logging.error(f"Error polling focuser position: {e}")
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
                search_width = 50
                bounds = (minima - search_width, minima + search_width)

                self._tk_root.event_generate(FocuserService.AutofocusEventName, when="tail", x=0, y=start_minima)

                fwhms = []

                for offset in [-search_width, search_width, -(search_width//2), (search_width//2)]:
                    pos = self._goto(minima + offset)
                    fwhms.append((minima + offset, self._snap(pos)))

                logging.info(f"Initial fwhm measurements: {fwhms}")
    
                # fit curve
                coeffs = np.polyfit([x[0] for x in fwhms], [x[1] for x in fwhms], deg=2)
                if coeffs[0] < 0:
                    # failed
                    logging.error(f"Fit failed: {coeffs}")
                    raise RuntimeError(f"Fit failed: {coeffs}")

                self._tk_root.event_generate(FocuserService.AutofocusEventName, when="tail", x=1, y=minima)

                # calc new minima
                minima = int(-coeffs[1]/(2*coeffs[0]))
                tgt_fwhm = np.polyval(coeffs, minima)
                if minima < bounds[0]:
                    minima = bounds[0]
                elif minima > bounds[1]:
                    minima = bounds[1]
                
                logging.info(f"Autofocus minima at {minima}, fwhm = {tgt_fwhm}")

                pos = self._goto(minima)
                fwhms.append((minima + offset, fwhm := self._snap(pos)))

                sign = 1
                delta = 1
                while fwhm > tgt_fwhm + 1 and delta < search_width:
                    minima += sign * delta
                    delta = delta * 2
                    sign = -sign
                    pos = self._goto(minima)
                    fwhms.append((minima, fwhm := self._snap(pos)))

                logging.info(f"Final fwhm measurements: {fwhms}")

                if fwhm > tgt_fwhm + 1:
                    # failed, go to best we have
                    min_pos = np.argmin([x[1] for x in fwhms])
                    logging.info(f"Autofocus did not reach target ({tgt_fwhm}), best fwhm {fwhm} at {fwhms[min_pos][0]}")
                    self._goto(fwhms[min_pos][0])
                    self._tk_root.event_generate(FocuserService.AutofocusEventName, when="tail", x=2, y=fwhms[min_pos][0])
                    return
                else:
                    logging.info(f"Autofocus reached target ({tgt_fwhm}), final fwhm {fwhm} at {minima}")

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
            "iso": 300,
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

    def _goto(self, position):
        if self._focuser is None or not self._focuser.connected:
            raise RuntimeError("Focuser not connected")
        retry = 3
        while (curr_position:=self._focuser.position) != position and retry > 0:
            self._focuser.goto(position)
            retry -= 1
            time.sleep(1)
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
