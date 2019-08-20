#-*- coding: utf-8 -*-
"""
Laser management.

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import time
import numpy as np
from qtpy import QtCore

from core.module import Connector, ConfigOption
from logic.generic_logic import GenericLogic
from interface.simple_laser_interface import ControlMode, ShutterState, LaserState


class M2LaserLogic(GenericLogic):
    """ Logic module agreggating multiple hardware switches.
    """
    _modclass = 'm2laser'
    _modtype = 'logic'

    # waiting time between queries im milliseconds
    laser = Connector(interface='M2LaserInterface')
    queryInterval = ConfigOption('query_interval', 100) #needed for wavemeter

    sigUpdate = QtCore.Signal()

    def on_activate(self):
        """ Prepare logic module for work.
        """
        self._laser = self.laser()
        self.stopRequest = False
        self.bufferLength = 100 #?
        self.data = {}

        # delay timer for querying laser
        self.queryTimer = QtCore.QTimer()
        self.queryTimer.setInterval(self.queryInterval)
        self.queryTimer.setSingleShot(True)

        #everytime queryTimer timeout emits a signal, run check_laser_loop
        self.queryTimer.timeout.connect(self.check_laser_loop, QtCore.Qt.QueuedConnection)

        # get laser capabilities
        self.laser_state = self._laser.get_laser_state() #??unused?

        self.current_wavelength = self._laser.get_wavelength() #?unused? initializing?


        self.init_data_logging()
        self.start_query_loop() #why put this here also?

    def on_deactivate(self):
        """ Deactivate modeule.
        """
        print('TRYING TO DEACTIVATE in logic')
        self.stop_query_loop()
        for i in range(5):
            time.sleep(self.queryInterval / 1000)
            QtCore.QCoreApplication.processEvents()

    @QtCore.Slot()
    def check_laser_loop(self):
        """ Get power, current, shutter state and temperatures from laser. """
        if self.stopRequest:
            if self.module_state.can('stop'):
                self.module_state.stop()
            self.stopRequest = False
            return
        qi = self.queryInterval
        try:
            #print('laserloop', QtCore.QThread.currentThreadId())
            self.laser_state = self._laser.get_laser_state() #! look at
            self.current_wavelength = self._laser.get_wavelength()

            #unused below??
            for k in self.data:
                self.data[k] = np.roll(self.data[k], -1)

     #       for k, v in self.laser_temps.items():
     #           self.data[k][-1] = v
        except:
            qi = 3000
            self.log.exception("Exception in laser status loop, throttling refresh rate.")

        self.queryTimer.start(qi)
        self.sigUpdate.emit()

    @QtCore.Slot()
    def start_query_loop(self):
        """ Start the readout loop. """
        self.module_state.run()
        self.queryTimer.start(self.queryInterval)

    @QtCore.Slot()
    def stop_query_loop(self):
        """ Stop the readout loop. """
        self.stopRequest = True
        for i in range(10):
            if not self.stopRequest:
                return
            QtCore.QCoreApplication.processEvents()
            time.sleep(self.queryInterval/1000)

    def init_data_logging(self):
        """ Zero all log buffers. """
        print('To implement')
    #    self.data['current'] = np.zeros(self.bufferLength)
    #    self.data['power'] = np.zeros(self.bufferLength)
    #    self.data['time'] = np.ones(self.bufferLength) * time.time()
    #    temps = self._laser.get_temperatures()
    #    for name in temps:
    #        self.data[name] = np.zeros(self.bufferLength)



