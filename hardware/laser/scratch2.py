from toptica.lasersdk.dlcpro.v1_6_3 import DLCpro, SerialConnection

import sys


import matplotlib.pyplot as pyplot

from toptica.lasersdk.utils.dlcpro import *


with DLCpro(SerialConnection('COM9')) as dlcpro:
    print(dlcpro.system_label.get())
    dlcpro.system_label.set('Please do not touch!')

    print(dlcpro.time.get())
    print(dlcpro.emission.get())
    #dlcpro.emission.set('True')
    print('continuing test')
    print(dlcpro.laser1.scan.frequency.get())

    dlcpro.laser1.dl.lock.close()
    #scope_data = extract_float_arrays('xyY', dlcpro.laser1.scope.data.get())
    #dlcpro.laser1.dl.lock.close()

###print(dlcpro.time.get())