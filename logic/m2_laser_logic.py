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
from logic.counter_logic import CounterLogic
from interface.simple_laser_interface import ControlMode, ShutterState, LaserState



from collections import OrderedDict
import matplotlib.pyplot as plt

from core.module import StatusVar
from logic.generic_logic import GenericLogic
from interface.slow_counter_interface import CountingMode
from core.util.mutex import Mutex



class M2LaserLogic(CounterLogic):


    """ Logic module agreggating multiple hardware switches.
    """
    _modclass = 'm2laser'
    _modtype = 'logic'

    # waiting time between queries im milliseconds
    laser = Connector(interface='M2LaserInterface')
    queryInterval = ConfigOption('query_interval', 100) #needed for wavemeter

    sigUpdate = QtCore.Signal()


###############fkjsflks
    sigCounterUpdated = QtCore.Signal()

    sigCountDataNext = QtCore.Signal()

    sigGatedCounterFinished = QtCore.Signal()
    sigGatedCounterContinue = QtCore.Signal(bool)
    sigCountingSamplesChanged = QtCore.Signal(int)
    sigCountLengthChanged = QtCore.Signal(int)
    sigCountFrequencyChanged = QtCore.Signal(float)
    sigSavingStatusChanged = QtCore.Signal(bool)
    sigCountStatusChanged = QtCore.Signal(bool)
    sigCountingModeChanged = QtCore.Signal(CountingMode)



    ## declare connectors
    counter1 = Connector(interface='SlowCounterInterface')
    savelogic = Connector(interface='SaveLogic')

    # status vars
    _count_length = StatusVar('count_length', 300)
    _smooth_window_length = StatusVar('smooth_window_length', 10)
    _counting_samples = StatusVar('counting_samples', 1)
    _count_frequency = StatusVar('count_frequency', 50)
    _saving = StatusVar('saving', False)




    def on_activate(self):
        # Connect to hardware and save logic
        print('on_activate is called')
        self._counting_device = self.counter1()
       #### self._save_logic = self.savelogic()

        # Recall saved app-parameters
        if 'counting_mode' in self._statusVariables:
            self._counting_mode = CountingMode[self._statusVariables['counting_mode']]

        constraints = self.get_hardware_constraints()
        number_of_detectors = constraints.max_detectors

        # initialize data arrays
        self.countdata = np.zeros([len(self.get_channels()), self._count_length])
        self.countdata_smoothed = np.zeros([len(self.get_channels()), self._count_length])
        self.rawdata = np.zeros([len(self.get_channels()), self._counting_samples])
        self._already_counted_samples = 0  # For gated counting
        self._data_to_save = []

        # Flag to stop the loop
        self.stopRequested = False

        self._saving_start_time = time.time()

        # connect signals
        self.sigCountDataNext.connect(self.count_loop_body, QtCore.Qt.QueuedConnection)


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


        #TODO keep for testing only
  ###      self.startCount() #will it work????

    def on_deactivate(self):
        #taken from counter_logic: (not sure if neccessary?)
        """ Deinitialisation performed during deactivation of the module.
        """
        # Save parameters to disk
        self._statusVariables['counting_mode'] = self._counting_mode.name

        # Stop measurement
        if self.module_state() == 'locked':
            self._stopCount_wait()

        self.sigCountDataNext.disconnect()

        #from laser_logic
        """ Deactivate modeule.
        """
        print('TRYING TO DEACTIVATE in logic')
        self.stop_query_loop()
        for i in range(5):
            time.sleep(self.queryInterval / 1000)
            QtCore.QCoreApplication.processEvents()


    #TODO be consistent in use of either QtCore.Slot (from laser logic) or counter_logic way of doing things
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

            #ADDED
    #####        self.count_loop_body()
            #THIS CURRENTLY WILL NOT RUN, probably because threads are locked. TODO FIX

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


    #overload from counter_logic.py
    def count_loop_body(self):
        """ This method gets the count data from the hardware for the continuous counting mode (default).

        It runs repeatedly in the logic module event loop by being connected
        to sigCountContinuousNext and emitting sigCountContinuousNext through a queued connection.
        """
        print('count_loop_body runs')
        if self.module_state() == 'locked':
            print('locked thread in count_loop_body is being accessed')
            with self.threadlock:
                # check for aborts of the thread in break if necessary
                if self.stopRequested:
                    # close off the actual counter
                    cnt_err = self._counting_device.close_counter()
                    clk_err = self._counting_device.close_clock()
                    if cnt_err < 0 or clk_err < 0:
                        self.log.error('Could not even close the hardware, giving up.')
                    # switch the state variable off again
                    self.stopRequested = False
                    self.module_state.unlock()
                    self.sigCounterUpdated.emit()
                    return

                #ADDED: read the current wavelength value


                # read the current counter value
                self.rawdata = self._counting_device.get_counter(samples=self._counting_samples)
                print('this is rawdata')
                print(self.rawdata)
                #or this way, I can check the wavelength right before and right after I get a count :/
                #and then average them to assign the "wavelength" the counts were taken at

                #ADDED: read the current wavelength value
                self.wavelengthdata = self._laser.get_wavelength()
                #redefine another counter_logic func so this gets put into an array and used!

                #alternatively, view confocal or odmr_logic - they also have to tie together another variable with counts
                #Also reading the current wavelength value better be much much faster than the clock speed

                if self.rawdata[0, 0] < 0:
                    self.log.error('The counting went wrong, killing the counter.')
                    self.stopRequested = True
                else:
                    if self._counting_mode == CountingMode['CONTINUOUS']:
                        self._process_data_continous()
                    elif self._counting_mode == CountingMode['GATED']:
                        self._process_data_gated()
                    elif self._counting_mode == CountingMode['FINITE_GATED']:
                        self._process_data_finite_gated()
                    else:
                        self.log.error('No valid counting mode set! Can not process counter data.')

            # call this again from event loop
            self.sigCounterUpdated.emit()
            self.sigCountDataNext.emit()
        return
