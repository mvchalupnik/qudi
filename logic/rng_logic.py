from core.module import Connector
from logic.generic_logic import GenericLogic
from qtpy import QtCore
import time


class RNGLogic(GenericLogic):
    """Tutorial logic to interact with random number generator
    """

    _modclass = 'RNGLogic'
    _modtype = 'logic'

    rng = Connector(interface='DoesNotMatter')  # interface='RNGInterface'

    # stop_sig = QtCore.Signal()
    repeat_sig = QtCore.Signal()

    def on_activate(self):
        """ Initialisation performed during activation of the module.
        """
        # Connect to hardware
        self._rng = self.rng()

        # Monitor quasi-loop
        self._value_list = None
        self._isMonitoring = False
        self.repeat_sig.connect(self.loop_step, QtCore.Qt.QueuedConnection)

        # Monitor settings
        self._monitor_update_rate = 1
        self._monitor_samples_number = 1

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        if self._isMonitoring:
            self.stop_monitoring()

    # ===================================================
    # RNG hardware methods

    def set_rng_params(self, mean=None, noise=None):
        self._rng.set_params(mean, noise)

    def get_rng_params(self):
        return self._rng.get_params()

    def get_random_value(self, samples_number=1):
        return self._rng.get_random_value(samples_number)

    # ===================================================
    # Monitor methods

    # Start/stop/make_next_step quasi-loop
    def start_monitoring(self):
        self._isMonitoring = True
        self.repeat_sig.emit()

    def stop_monitoring(self):
        self._isMonitoring = False

    def loop_step(self):
        if self._isMonitoring:
            self._value_list = self._rng.get_random_value(samples_number=self._monitor_samples_number)
            print(self._value_list)
            time.sleep(1/self._monitor_update_rate)
            self.repeat_sig.emit()

    # set/get monitor settings
    def set_monitor_params(self, update_rate=None, samples_number=None):
        if update_rate is not None:
            self._monitor_update_rate = update_rate
        if samples_number is not None:
            self._monitor_samples_number = samples_number

    def get_monitor_params(self):
        param_dict = {
            'update_rate': self._monitor_update_rate,
            'samples_number': self._monitor_samples_number
        }
        return param_dict

    def get_current_value(self):
        if self._isMonitoring:
            return self._value_list
        else:
            return None
