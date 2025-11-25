import base64
from datetime import datetime
import time
import math
import json
import numpy as np
import requests
import shutil


ip="127.0.0.1"
port=8090
password=""

def chk_ret(r):
    assert(r.status_code == 200)
    if not r.text == 'ok':
        raise Exception(r)

#s = StellariumRC.Stellarium() # you can pass the host, port and password (if any) as parameters
# print(s.main.getStatus()) # get the current state of Stellarium

r = requests.get(f"http://{ip}:{port}/api/main/status",auth=("",password))
try:
    # pretty-print the full JSON response to avoid truncated repr
    data = r.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
except ValueError:
    # fallback to raw text if response is not valid JSON
    print(r.text)

r = requests.post(f"http://{ip}:{port}/api/location/setlocationfields",
                         params={
                                "latitude":39,
                                "longitude":-74,
                                "altitude":0,
                         },auth=("",password))
chk_ret(r)

r = requests.post(f"http://{ip}:{port}/api/main/time", 
                          data={"timerate":0},auth=("",password))
chk_ret(r)
jd = datetime(2000, 11, 10, 22, 0, 0).timestamp() / 86400.0 + 2440587.5
r = requests.post(f"http://{ip}:{port}/api/main/time", 
                    data={"time":jd},auth=("",password))
chk_ret(r)
# s.main.setFocus("Polaris", mode='center')

def setView(altDeg, azDeg):
    altRad = np.deg2rad(altDeg)
    azRad = np.deg2rad(azDeg)
    r = requests.post(f"http://{ip}:{port}/api/main/view", 
                          data={
                                "coord":"altAz",
                                "ref": "auto",
                                "alt":altRad,
                                "az":azRad,
                          },auth=("",password))
    chk_ret(r)


r = requests.get(f"http://{ip}:{port}/api/stelaction/list", auth=("",password))
with open('stelaction_list_response.txt', 'wb') as f:
    try:
        r.raise_for_status()

        for chunk in r.iter_content(chunk_size=8192):
            if not chunk:
                continue
            try:
                f.write(chunk.decode('utf-8'))
            except Exception:
                f.write(chunk)
    except Exception as e:
        print("Error reading response:", e)

def setProp(prop, val):
    r = requests.post(f"http://{ip}:{port}/api/stelproperty/set?id={prop}&value={val}", auth=("",password))
    assert(r.status_code == 200)

setProp("StelGui.autoHideVerticalButtonBar", "true")
setProp("StelGui.autoHideHorizontalButtonBar", "true")
setProp("actionAutoHideHorizontalButtonBar", "true")
setProp("actionAutoHideVerticalButtonBar", "true")
setProp("actionShow_DateTime_Window_Global", "false")
setProp("Oculars.flagGuiPanelEnabled", "false")
setProp("LandscapeMgr.currentLandscapeID", "zero")
setProp("LandscapeMgr.cardinalPointsDisplayed", "false")
setProp("ConstellationMgr.linesDisplayed", "false")
setProp("ConstellationMgr.namesDisplayed", "false")
setProp("GridLinesMgr.celestialPolesDisplayed", "false")
setProp("GroundGridMgr.horizonDisplayed", "false")
setProp("NebulaMgr.flagOutlinesDisplayed", "false")
setProp("NebulaMgr.flagHintDisplayed", "false")
setProp("NebulaMgr.flagAdditionalNamesDisplayed", "false")
setProp("AsterismMgr.namesDisplayed", "false")
setProp("MeteorShowers.enableLabels", "false")
setProp("MilkyWay.flagMilkyWayDisplayed", "false")
setProp("actionShow_MeteorShowers", "false")
setProp("LandscapeMgr.labelsDisplayed", "false")
setProp("MainView.flagOverwriteScreenshots", "true")
setProp("StelGui.visible", "false")
setProp("Satellites.flagHintsVisible", "false")


def labels_off():
    setProp("GridLinesMgr.gridlinesDisplayed", "false")
    setProp("SolarSystem.labelsDisplayed", "false")
    setProp("StarMgr.flagAdditionalNamesDisplayed", "false")
    setProp("StarMgr.flagLabelsDisplayed", "false")

def labels_on():
    setProp("GridLinesMgr.gridlinesDisplayed", "true")
    setProp("SolarSystem.labelsDisplayed", "true")
    setProp("StarMgr.flagAdditionalNamesDisplayed", "true")
    setProp("StarMgr.flagLabelsDisplayed", "true")


r = requests.post(f"http://{ip}:{port}/api/main/fov", 
                          data={"fov":100},auth=("",password))
chk_ret(r)

def doAction(action):
    r = requests.post(f"http://{ip}:{port}/api/stelaction/do?id={action}", auth=("",password))
    chk_ret(r)

from itertools import product

# for alt,az in product([30.0, 45.0], [0.0, 90.0, 180.0, 270.0]):
#     labels_off()
#     setView(alt, az)
#     time.sleep(1.0)
#     doAction("actionSave_Screenshot_Global")
#     time.sleep(1.0)
#     shutil.move(r"C:\Users\anand\OneDrive\Pictures\Stellarium\stellarium-001.png",
#                 f"./stellarium_explore/sky_alt{alt}_az{az}.png")
    
#     labels_on()
#     time.sleep(1.0)
#     doAction("actionSave_Screenshot_Global")
#     time.sleep(1.0)
#     shutil.move(r"C:\Users\anand\OneDrive\Pictures\Stellarium\stellarium-001.png",
#                 f"./stellarium_explore/sky_alt{alt}_az{az}_label.png")


#     with open(f'./stellarium_explore/sky_alt{alt}_az{az}_info.json', 'w', encoding='utf-8') as f:
#         r = requests.get(f"http://{ip}:{port}/api/main/status",auth=("",password))
#         try:
#             # pretty-print the full JSON response to avoid truncated repr
#             data = r.json()
#             f.write(json.dumps(data, indent=2, ensure_ascii=False))
#         except ValueError:
#             # fallback to raw text if response is not valid JSON
#             f.write(r.text)



# South
# setView(30.0, 0.0)
# East
# setView(30.0, 90.0)
# North
setView(45.0, 180.0)
# West
# setView(30.0, 270.0)
# altAz = json.loads(s.main.getView()['altAz'])
# print('Alt:', math.asin(altAz[2]) * 180.0 / math.pi)
# print('Az:', math.atan2(altAz[1], altAz[0]) * 180.0 / math.pi)
labels_on()
# doAction("actionSave_Screenshot_Global")

time.sleep(1)


