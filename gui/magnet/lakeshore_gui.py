"""
M. Chalupnik
Lakeshore Superconducting magnet power supply
Qudi GUI file
"""

from gui.guibase import GUIBase
import os
from core.module import Connector

from qtpy import QtWidgets
from qtpy import QtGui
from qtpy import uic
from qtpy import QtCore
import time
import numpy as np

class MagnetWindow(QtWidgets.QMainWindow):
    def __init__(self):
        """ Create the magnet control window."""
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'lakeshore_basic2.ui')

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class MagnetGUI(GUIBase):
    _modclass = 'magnetgui'
    _modtype = 'gui'

    ## declare connectors
    magnetlogic = Connector(interface='LakeshoreLogic')

    sigStopTimer = QtCore.Signal()
    sigStartTimer = QtCore.Signal()
    sigSetFields = QtCore.Signal()
    sigSetPSH = QtCore.Signal()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """
        self._magnet_logic = self.magnetlogic()


        #connect signals
        self._magnet_logic.sigGuiUpdate.connect(self.updateMeasuredVals)


        self.sigStopTimer.connect(self._magnet_logic.stop_query_loop)
        self.sigStartTimer.connect(self._magnet_logic.start_query_loop)
        self.sigSetFields.connect(self._magnet_logic.set_field)
        self.sigSetPSH.connect(self._magnet_logic.set_psh)

        # setting up the window
        self._mw = MagnetWindow()

        #Set up help display
        self._mw.actionHelp.triggered.connect(self.displayHelp)

        #Set up calculation of X, Y, Z on change of theta, phi, or field magnitude
        self._mw.doubleSpinBox_theta.valueChanged.connect(self.updateCalcVals)
        self._mw.doubleSpinBox_phi.valueChanged.connect(self.updateCalcVals)
        self._mw.doubleSpinBox_setfield.valueChanged.connect(self.updateCalcVals)

        #Button connections
        self._mw.pushButton_setField.clicked.connect(self.setFields)

        self._mw.radioButton_PSH_on.clicked.connect(self.setPSH)
        self._mw.radioButton_PSH_off.clicked.connect(self.setPSH)


        self.updateCalcVals()
        self._mw.show()


    #on hide?
    #on show?


    def on_deactivate(self):
        pass

    def updateMeasuredVals(self, arr):
        xmval = arr[0]
        ymval = arr[1]
        zmval = arr[2]
        xpsh = arr[3]
        ypsh = arr[4]
        zpsh = arr[5]
        self._mw.x_field_meas.setText('{:.4f}'.format(xmval))
        self._mw.y_field_meas.setText('{:.4f}'.format(ymval))
        self._mw.z_field_meas.setText('{:.4f}'.format(zmval))

        self._mw.fieldmagnitude_reading.setText('{:.4f}'.format(np.sqrt(xmval**2 + ymval**2 + zmval**2)))

        #Set PSH status
        self._mw.x_psh_status_label.setText(self.translateStatus(xpsh))
        self._mw.y_psh_status_label.setText(self.translateStatus(ypsh))
        self._mw.z_psh_status_label.setText(self.translateStatus(zpsh))

    def updateCalcVals(self):
        # grab phi and theta unit sphere angles
        theta = self._mw.doubleSpinBox_theta.value()
        phi = self._mw.doubleSpinBox_phi.value()

        # convert to unit vectors x y z
        xhat = np.sin(theta) * np.cos(phi)
        yhat = np.sin(theta) * np.sin(phi)
        zhat = np.cos(theta)

        # grab field magnitude; find xset, yset, zset
        mag = self._mw.doubleSpinBox_setfield.value()
        xset = xhat * mag
        yset = yhat * mag
        zset = zhat * mag

        self._mw.x_field_set.setText('{:.4f}'.format(xset))
        self._mw.y_field_set.setText('{:.4f}'.format(yset))
        self._mw.z_field_set.setText('{:.4f}'.format(zset))



    def setFields(self):

        #first make sure calc vals are updated (though they should be; this is most likely unencessary)
        self.updateCalcVals()

        #set values acessible by logic (can't pass in the signal; python complains it doesn't want to stop the thread)
        self._magnet_logic.field_set_val_x = float(self._mw.x_field_set.text())
        self._magnet_logic.field_set_val_y = float(self._mw.y_field_set.text())
        self._magnet_logic.field_set_val_z = float(self._mw.z_field_set.text())

        self.sigSetFields.emit()

    def setPSH(self):
        if self._mw.radioButton_PSH_on.isChecked() and not self._mw.radioButton_PSH_off.isChecked():
            self._magnet_logic.psh_set_val = 1
            self.sigSetPSH.emit()
        elif self._mw.radioButton_PSH_off.isChecked() and not self._mw.radioButton_PSH_on.isChecked():
            self._magnet_logic.psh_set_val = 0
            self.sigSetPSH.emit()
        else:
            self.log.error('PSH read error, please check the equipment!')

    def translateStatus(self, s):
        if s== 0:
            return "Heater off"
        if s == 1:
            return "Heater on"
        if s == 2:
            return "Heater warming"
        if s == 3:
            return "Heater cooling"
        else:
            return "Error in PSH status"

    def displayHelp(self):
        msg = QtWidgets.QMessageBox()
        txt = 'The output current setting is not allowed to change while the persistent switch heater is warming or ' \
              'cooling. The amount of time it takes for the PSH to warm or cool is system dependent and can be setup ' \
              'under the PSH Setup key. \n \n' \
              'If you ramp the current with the PSH off, you will get an erroneous field reading (calculated from the ' \
              'current reading).In reality, magnetic field does not change when current is ramped with PSH off, and ' \
              'the displayed current is not in the magnet but elsewhere. \n \n ' \
              'When turning on the PSH, it is important that the output current setting of the power supply is equal ' \
              'to the current in the magnet. If the currents are not equal when the PSH is turned on, there is a ' \
              'possibility that the magnet can quench. The Model 625 adds an extra layer of protection to keep this ' \
              'from happening. The Model 625 stores the output current setting of the supply when the PSH was turned ' \
              'off last. If the output current setting does not match this stored setting when the PSH is being turned ' \
              'on, the following message screen will appear. \n \n ' \
              'SOP: \n 1. Ensure set values equal measured values \n 2. Turn on PSH, wait for heat up \n ' \
              '3. Change Field as desired; watch that magnet temp stays below 4.8K \n 4. Turn off PSH \n \n ' \
              'Note: Please take care to wait for PSH to settle on "on" or "off" before toggling on or off or ' \
              'trying to send a new field change to the magnet. Likewise, please wait for the magnet field to ' \
              'stabilize after changing the field value before attempting to send additional changes to the ' \
              'magnets. (Todo, handle this in code to prevent user error, won\'t be difficult)'
        msg.setText(txt)
        msg.exec_()