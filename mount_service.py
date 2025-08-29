from service_base import ServiceBase
from capture_service import CaptureService
from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.coordinates import ICRS
import time
import numpy as np
from datetime import datetime
from astropy.io import fits
from image_data import ImageData
import threading
import skymap.platesolver as PS
from skymap.skymap import SkyMap
import psutil
from settings import config
from copy import deepcopy


class MountService(ServiceBase):

    PositionUpdateEventName = "<<mount_position_update>>"

    def __init__(self, tk_root, mount, camera_svc):
        super().__init__(tk_root)
        self._mount = mount
        self._camera_svc = camera_svc
        self._tk_root.after(1000, self._poll_mount_position)

        self._mtx = threading.Lock()
        self._status = "Unk"
        self._coord = None
        self._coord_txt = ""
        self._skyMap = None

    def on_start(self):
        # Load skymap
        try:
            if "mongod.exe" not in [p.name() for p in psutil.process_iter()]:
                psutil.Popen([r"mongod.exe", "--dbpath", config['stardb']], shell=True, cwd=config['mongodir'])
            with self._mtx:
                self._skyMap = SkyMap()
        except Exception as ex:
            print(f"Failed to connect to SkyMap: {ex}")

    def _publish_mount_position(self):
        if self._mount is not None and self._mount.connected:
            with self._mtx:
                if self._mount.tracking:
                    self._status = "Tracking"
                elif self._mount.atpark:
                    self._status = "Parked"
                elif self._mount.slewing:
                    self._status = "Slewing"

                self._coord = self._mount.coordinates
                self._coord_txt = self._coord.to_string("hmsdms")
                self._objname = self._getObjectName(self._coord)
            self._tk_root.event_generate(MountService.PositionUpdateEventName, when="tail")

    def _poll_mount_position(self):
        self._publish_mount_position()
        self._tk_root.after(5000, self._poll_mount_position)

    def _getObjectName(self, coord):
        try:
            if self._skyMap is None:
                return ""
            result = self._skyMap.findObjects(coord, limit=1)
            return result
        except Exception as ex:
            print(f"Failed to get name from SkyMap: {ex}")
            return ""

    def getMountInfo(self):
        with self._mtx:
            return deepcopy({
                "status": self._status,
                "coord": self._coord,
                "coord_txt": self._coord_txt,
                "object_name": self._objname
            })

    def goto(self, coord: SkyCoord, on_success=None, on_failure=None):
        return self.start_job({'cmd': 'goto', 'coord': coord}, on_success=on_success, on_failure=on_failure)
    
    def syncto(self, coord: SkyCoord, on_success=None, on_failure=None):
        return self.start_job({'cmd': 'syncto', 'coord': coord}, on_success=on_success, on_failure=on_failure)
    
    def park(self, on_success=None, on_failure=None):
        return self.start_job({'cmd': 'park'}, on_success=on_success, on_failure=on_failure)

    def searchName(self, term):
        return self._skyMap.searchText(term) if self._skyMap else []
    
    def search_catalog(self, cat_name, m):
        return self._skyMap.search_catalog(cat_name, m) if self._skyMap else []

    def refine(self, on_success=None, on_failure=None):
        return self.start_job({'cmd': 'refine'}, on_success=on_success, on_failure=on_failure)

    def process(self):

        if self._mount is not None and self._mount.connected:

            if self.job['cmd'] == 'goto':
                self._mount.moveto(self.job['coord'])

            elif self.job['cmd'] == 'syncto':
                self._mount.syncto(self.job['coord'])

            elif self.job['cmd'] == 'park':
                self._mount.park()

            elif self.job['cmd'] == 'refine':
                # Take snapshot
                imageData = self._camera_svc.run_job({
                    "object_name": "refine",
                    "focal_length": 0,
                    "latitude": None,
                    "longitude": None,
                    "iso": 200,
                    "exp": 5.0,
                    "image_type": "Light",
                    "output_fname": f"refine_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.fit"
                })
                if imageData is None:
                    raise RuntimeError("Capture failed")
                imageData.computeStars()
                solver_result = PS.platesolve(imageData, self._mount.coordinates)
                if solver_result is None:
                    raise RuntimeError("Plate solving failed")
                self.output = solver_result

        else:
            raise RuntimeError("Mount not connected")

