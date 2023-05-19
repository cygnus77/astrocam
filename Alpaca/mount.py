from enum import IntEnum
from datetime import datetime
import numpy as np
from struct import unpack
from subprocess import IDLE_PRIORITY_CLASS
import tempfile
import time
import typing as T
from astropy import units as u
from astropy.coordinates import SkyCoord

from Alpaca.alpaca_base import AscomDevice

class Mount(AscomDevice):
    def __init__(self, devNameKeyword: str):
        super().__init__("telescope", devNameKeyword)

    @property
    def coordinates(self) -> SkyCoord:
        ra = self._get("rightascension")
        dec = self._get("declination")
        return SkyCoord(ra * u.degree, dec * u.degree)

    @property
    def site_lat(self):
        return self._get("sitelatitude")

    @property
    def site_lat(self):
        return self._get("sitelongitude")

    @property
    def tracking(self):
        return self._get("tracking")

    @property
    def slewing(self):
        return self._get("slewing")

    @property
    def atpark(self):
        return self._get("atpark")

    def moveto(self, ra, dec):
        self._put("slewtocoordinatesasync", {
            "RightAscension": ra,
            "Declination": dec
        })

    def park(self):
        self._put("findhome", {})
        while not self._get("athome"):
            time.sleep(2)
        self._put("park", {})

    def unpark(self):
        self._put("unpark", {})

if __name__ == "__main__":
    m = Mount("Gemini")
    c = m.coordinates
    print(c.to_string("hmsdms"))
    m.park()
