"""
M. Chalupnik
Lakeshore Superconducting magnet power supply
Qudi Logic file
"""

from core.module import Connector
from logic.generic_logic import GenericLogic
import time
from qtpy import QtCore


class LakeshoreLogic(GenericLogic):
    """This logic module gathers data from wavemeter and the counter logic.
    """

    _modclass = 'sc_magnet_logic'
    _modtype = 'logic'

    # declare connectors
    magnet = Connector(interface='LakeshoreInterface')

    # set up Signals
    sigGuiUpdate = QtCore.Signal(list)

    def on_activate(self):
        self._magnets = self.magnet()

        #These are the set values used to communicate from the gui to tell logic and hardware to
        #set which values. Have to do it this way (rather than, say, passing these as signal parameters)
        # because set val process involves ending threads, and python is picky about where you can end threads from.
        self.field_set_val_x = 0
        self.field_set_val_y = 0
        self.field_set_val_z = 0

        self.psh_set_val = 0

        #set up queryTimer to query magnetic field at each power supply
        self.queryTimer = QtCore.QTimer()
        self.queryInterval = 100 #in milliseconds
        self.queryTimer.setInterval(self.queryInterval)
        self.queryTimer.setSingleShot(False)
        self.queryTimer.timeout.connect(self.query_fields, QtCore.Qt.QueuedConnection)

        self.start_query_loop()

    def on_deactivate(self):
        self.stop_query_loop()

    @QtCore.Slot()
    def start_query_loop(self):
        print('start_query_loop called in logic')
        self.queryTimer.start()

    @QtCore.Slot()
    def query_fields(self):
        ##Below very useful for debugging
        #print('testing')
        #print(time.time())

        meas_field_x = self._magnets.get_field(0)
        meas_field_y = self._magnets.get_field(1)
        meas_field_z = self._magnets.get_field(2)

        #Manual says: need to wait at least 100 ms between communications
        time.sleep(.105)

        psh_status_x = self._magnets.get_psh(0)
        psh_status_y = self._magnets.get_psh(1)
        psh_status_z = self._magnets.get_psh(2)

        #send signal to update GUI
        self.sigGuiUpdate.emit([meas_field_x, meas_field_y, meas_field_z, psh_status_x, psh_status_y, psh_status_z])

    @QtCore.Slot()
    def stop_query_loop(self):
        print('stop_query_loop called in logic')

        self.queryTimer.stop()
        for i in range(10):
            QtCore.QCoreApplication.processEvents()
            time.sleep(self.queryInterval / 1000)

    @QtCore.Slot()
    def set_field(self):
        print('setting field')

        self.queryTimer.stop()
        for i in range(10):
            QtCore.QCoreApplication.processEvents()
            time.sleep(self.queryInterval / 1000)

        self._magnets.set_field(0, self.field_set_val_x)
        self._magnets.set_field(1, self.field_set_val_y)
        self._magnets.set_field(2, self.field_set_val_z)

        #manual says make sure to wait at least 100 ms between communications with the drivers
        time.sleep(.120)

        self.start_query_loop()

    @QtCore.Slot()
    def set_psh(self):
        print('setting PSH')

        self.queryTimer.stop()
        for i in range(10):
            QtCore.QCoreApplication.processEvents()
            time.sleep(self.queryInterval / 1000)

        self._magnets.set_psh(0, self.psh_set_val)
        self._magnets.set_psh(1, self.psh_set_val)
        self._magnets.set_psh(2, self.psh_set_val)

        #manual says make sure to wait at least 100 ms between communications with the drivers
        time.sleep(.120)

        self.start_query_loop()