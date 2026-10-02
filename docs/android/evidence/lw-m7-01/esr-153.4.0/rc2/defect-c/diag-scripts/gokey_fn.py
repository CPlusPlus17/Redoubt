import re
from drv import *

def ime_touch(label):
    s = sh("dumpsys input", check=False)
    m = re.search(r"name='Window\{\w+ u0 InputMethod\}'.*?visible=(\w+).*?touchableRegion=([^,]*(?:,[^,]*)?)", s)
    r = (m.group(1), m.group(2)) if m else None
    log(label, "IME input window:", r)
    return r

