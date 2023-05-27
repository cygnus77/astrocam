from astropy import units as u
from astropy.coordinates import ICRS
from astropy.coordinates import SkyCoord, Latitude, Longitude

class SimulatedMount():
    
    def __init__(self) -> None:
        # 14 15 39.67207	+19 10 56.6730
        self._coordinates = SkyCoord("14h15m39.67s +19d10m56.67s", frame=ICRS)
        self._site = SkyCoord(Longitude([-74, 20, 42], unit=u.deg),
                              Latitude([40, 51, 55], unit=u.deg),
                              frame=ICRS)
        return
    
    def close(self):
        return
    
    @property
    def coordinates(self) -> SkyCoord:
        return self._coordinates

    @property
    def site_lat(self):
        return self._site.lat

    @property
    def site_lat(self):
        return self._site.lon

    @property
    def tracking(self):
        return True

    @property
    def slewing(self):
        return False

    @property
    def atpark(self):
        return False

    def moveto(self, ra, dec):
        self.coordinates = SkyCoord(ra * u.degree, dec * u.degree)

    def park(self):
        return

    def unpark(self):
        return
