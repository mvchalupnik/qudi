import numpy as np
import os
import sys

from core.module import Connector
from gui.guibase import GUIBase
from gui.colordefs import QudiPalettePale as palette
from qtpy import QtWidgets
from qtpy import QtCore
from qtpy import uic


class RNGGui(GUIBase):
    _modclass = 'rnggui'
    _modtype = 'gui'

    # declare connectors
    rnglogic = Connector(interface='RNGLogic')

    # Signals
    # sigStart = QtCore.Signal()
    # sigStop = QtCore.Signal()

    def on_activate(self):
        # Connect to logic
        self._rng_logic = self.rnglogic()

        # instantiate MainWindow
        self._mw = RNGMainWindow()

        # Signal connection to logic module
        self._mw.startButton.clicked.connect(self._rng_logic.start_monitoring)
        self._mw.stopButton.clicked.connect(self._rng_logic.stop_monitoring)

        self._mw.mean_box.valueChanged.connect(self.mean_changed)
        self._mw.noise_box.valueChanged.connect(self.noise_changed)
        self._mw.update_rate_box.valueChanged.connect(self.update_rate_changed)

        self._rng_logic.repeat_sig.connect(
            self.new_random_value_received
        )

    def on_deactivate(self):
        pass
        # self._mw.startButton.clicked.disconnect()
        # self._mw.startButton.clicked.disconnect()
        # self._mw.mean_box.valueChanged.disconnect()
        # self._mw.noise_box.valueChanged.disconnect()
        # self._mw.update_rate_box.valueChanged.disconnect()
        # self._rng_logic._monitor_thread.value_updated_sig.disconnect()

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    def mean_changed(self, new_mean):
        self._rng_logic.set_rng_params(mean=new_mean)

    def noise_changed(self, new_noise):
        self._rng_logic.set_rng_params(noise=new_noise)

    def update_rate_changed(self, new_update_rate):
        self._rng_logic.set_monitor_params(update_rate=new_update_rate)

    def new_random_value_received(self):
        try:
            new_value = self._rng_logic.get_current_value()[0]
            self._mw.display.display(new_value)
        except:
            return


class RNGMainWindow(QtWidgets.QMainWindow):
    """ Create the Main Window based on the *.ui file. """

    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_rng.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = RNGMainWindow()

    sys.exit(app.exec_())
