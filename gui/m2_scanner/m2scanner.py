# -*- coding: utf-8 -*-
"""
This module contains a GUI for operating the spectrum logic module.

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

import os
import pyqtgraph as pg
import numpy as np

from core.module import Connector
from core.util import units
from gui.colordefs import QudiPalettePale as palette
from gui.guibase import GUIBase
from gui.fitsettings import FitSettingsDialog, FitSettingsComboBox
from qtpy import QtCore
from qtpy import QtWidgets
from qtpy import uic


class M2ControllerWindow(QtWidgets.QMainWindow):

    def __init__(self):
        """ Create the laser scanner window.
        """
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_m2scanner.ui') #modified

        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        self.show()


class M2ScannerGUI(GUIBase):
    _modclass = 'M2LaserGui'
    _modtype = 'gui'

    # declare connectors
    laserlogic = Connector(interface='M2LaserLogic')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

    def on_activate(self):
        """ Definition and initialisation of the GUI.
        """

        self._laser_logic = self.laserlogic()

        # setting up the window
        self._mw = M2ControllerWindow()



        self._laser_logic.sigUpdate.connect(self.updateGui)

        self._mw.scanType_comboBox.setInsertPolicy = 6  # InsertAlphabetically
        self._mw.scanType_comboBox.addItems({"Fine","Medium"})

        self._mw.scanRate_comboBox.setInsertPolicy = 6 #InsertAlphabetically
        for x in range(0, 14):
            self._mw.scanRate_comboBox.addItem(str(x))

        self._mw.scanType_comboBox.currentIndexChanged.connect(self.update_calculated_scan_params)
        self._mw.scanRate_comboBox.currentIndexChanged.connect(self.update_calculated_scan_params)
        self._mw.startWvln_doubleSpinBox.valueChanged.connect(self.update_calculated_scan_params)
        self._mw.stopWvln_doubleSpinBox.valueChanged.connect(self.update_calculated_scan_params)

        self.update_calculated_scan_params() #initialize


    #     self._mw.stop_diff_spec_Action.setEnabled(False)
    #     self._mw.resume_diff_spec_Action.setEnabled(False)
    #     self._mw.correct_background_Action.setChecked(self._spectrum_logic.background_correction)
    #
    #     # giving the plots names allows us to link their axes together
    #     self._pw = self._mw.plotWidget  # pg.PlotWidget(name='Counter1')
    #     self._plot_item = self._pw.plotItem
    #
    #     # create a new ViewBox, link the right axis to its coordinate system
    #     self._right_axis = pg.ViewBox()
    #     self._plot_item.showAxis('right')
    #     self._plot_item.scene().addItem(self._right_axis)
    #     self._plot_item.getAxis('right').linkToView(self._right_axis)
    #     self._right_axis.setXLink(self._plot_item)
    #
    #     # create a new ViewBox, link the right axis to its coordinate system
    #     self._top_axis = pg.ViewBox()
    #     self._plot_item.showAxis('top')
    #     self._plot_item.scene().addItem(self._top_axis)
    #     self._plot_item.getAxis('top').linkToView(self._top_axis)
    #     self._top_axis.setYLink(self._plot_item)
    #     self._top_axis.invertX(b=True)
    #
    #     # handle resizing of any of the elements
    #
    #     self._pw.setLabel('left', 'Fluorescence', units='counts/s')
    #     self._pw.setLabel('right', 'Number of Points', units='#')
    #     self._pw.setLabel('bottom', 'Wavelength', units='m')
    #     self._pw.setLabel('top', 'Relative Frequency', units='Hz')
    #
    #     # Create an empty plot curve to be filled later, set its pen
    #     self._curve1 = self._pw.plot()
    #     self._curve1.setPen(palette.c1, width=2)
    #
    #     self._curve2 = self._pw.plot()
    #     self._curve2.setPen(palette.c2, width=2)
    #
    #     self.update_data()
    #
    #     # Connect singals
    #     self._mw.rec_single_spectrum_Action.triggered.connect(self.record_single_spectrum)
    #     self._mw.start_diff_spec_Action.triggered.connect(self.start_differential_measurement)
    #     self._mw.stop_diff_spec_Action.triggered.connect(self.stop_differential_measurement)
    #     self._mw.resume_diff_spec_Action.triggered.connect(self.resume_differential_measurement)
    #
    #     self._mw.save_spectrum_Action.triggered.connect(self.save_spectrum_data)
    #     self._mw.correct_background_Action.triggered.connect(self.correct_background)
    #     self._mw.acquire_background_Action.triggered.connect(self.acquire_background)
    #     self._mw.save_background_Action.triggered.connect(self.save_background_data)
    #
    #     self._mw.restore_default_view_Action.triggered.connect(self.restore_default_view)
    #
    #     self._spectrum_logic.sig_specdata_updated.connect(self.update_data)
    #     self._spectrum_logic.spectrum_fit_updated_Signal.connect(self.update_fit)
    #     self._spectrum_logic.fit_domain_updated_Signal.connect(self.update_fit_domain)
    #
        self._mw.show()
    #
    #     self._save_PNG = True
    #
    #     # Internal user input changed signals
    #     self._mw.fit_domain_min_doubleSpinBox.valueChanged.connect(self.set_fit_domain)
    #     self._mw.fit_domain_max_doubleSpinBox.valueChanged.connect(self.set_fit_domain)
    #
    #     # Internal trigger signals
    #     self._mw.do_fit_PushButton.clicked.connect(self.do_fit)
    #     self._mw.fit_domain_all_data_pushButton.clicked.connect(self.reset_fit_domain_all_data)
    #
    #     # fit settings
    #     self._fsd = FitSettingsDialog(self._spectrum_logic.fc)
    #     self._fsd.sigFitsUpdated.connect(self._mw.fit_methods_ComboBox.setFitFunctions)
    #     self._fsd.applySettings()
    #     self._mw.action_FitSettings.triggered.connect(self._fsd.show)

    def on_deactivate(self):
        """ Deinitialisation performed during deactivation of the module.
        """
        # disconnect signals
#        self._fsd.sigFitsUpdated.disconnect()
        print('in gui trying to deactivate')
        self._mw.close()
#        self._laser_logic.on_deactivate() #problem when gui is closed, it's not actually deactivating :(
#        self._laser_logic._laser.on_deactivate()

    def show(self):
        """Make window visible and put it above all other windows.
        """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()

    # def update_data(self):
    #     """ The function that grabs the data and sends it to the plot.
    #     """
    #     data = self._spectrum_logic.spectrum_data
    #
    #     # erase previous fit line
    #     self._curve2.setData(x=[], y=[])
    #
    #     # draw new data
    #     self._curve1.setData(x=data[0, :], y=data[1, :])
    #
    # def update_fit(self, fit_data, result_str_dict, current_fit):
    #     """ Update the drawn fit curve and displayed fit results.
    #     """
    #     if current_fit != 'No Fit':
    #         # display results as formatted text
    #         self._mw.spectrum_fit_results_DisplayWidget.clear()
    #         try:
    #             formated_results = units.create_formatted_output(result_str_dict)
    #         except:
    #             formated_results = 'this fit does not return formatted results'
    #         self._mw.spectrum_fit_results_DisplayWidget.setPlainText(formated_results)
    #
    #         # redraw the fit curve in the GUI plot.
    #         self._curve2.setData(x=fit_data[0, :], y=fit_data[1, :])
    #
    # def record_single_spectrum(self):
    #     """ Handle resume of the scanning without resetting the data.
    #     """
    #     self._spectrum_logic.get_single_spectrum()
    #
    # def start_differential_measurement(self):
    #
    #     # Change enabling of GUI actions
    #     self._mw.stop_diff_spec_Action.setEnabled(True)
    #     self._mw.start_diff_spec_Action.setEnabled(False)
    #     self._mw.rec_single_spectrum_Action.setEnabled(False)
    #     self._mw.resume_diff_spec_Action.setEnabled(False)
    #
    #     self._spectrum_logic.start_differential_spectrum()
    #
    # def stop_differential_measurement(self):
    #     self._spectrum_logic.stop_differential_spectrum()
    #
    #     # Change enabling of GUI actions
    #     self._mw.stop_diff_spec_Action.setEnabled(False)
    #     self._mw.start_diff_spec_Action.setEnabled(True)
    #     self._mw.rec_single_spectrum_Action.setEnabled(True)
    #     self._mw.resume_diff_spec_Action.setEnabled(True)
    #
    # def resume_differential_measurement(self):
    #     self._spectrum_logic.resume_differential_spectrum()
    #
    #     # Change enabling of GUI actions
    #     self._mw.stop_diff_spec_Action.setEnabled(True)
    #     self._mw.start_diff_spec_Action.setEnabled(False)
    #     self._mw.rec_single_spectrum_Action.setEnabled(False)
    #     self._mw.resume_diff_spec_Action.setEnabled(False)
    #
    # def save_spectrum_data(self):
    #     self._spectrum_logic.save_spectrum_data()
    #
    # def correct_background(self):
    #     self._spectrum_logic.background_correction = self._mw.correct_background_Action.isChecked()
    #
    # def acquire_background(self):
    #     self._spectrum_logic.get_single_spectrum(background=True)
    #
    # def save_background_data(self):
    #     self._spectrum_logic.save_spectrum_data(background=True)
    #
    # def do_fit(self):
    #     """ Command spectrum logic to do the fit with the chosen fit function.
    #     """
    #     fit_function = self._mw.fit_methods_ComboBox.getCurrentFit()[0]
    #     self._spectrum_logic.do_fit(fit_function)
    #
    # def set_fit_domain(self):
    #     """ Set the fit domain in the spectrum logic to values given by the GUI spinboxes.
    #     """
    #     lambda_min = self._mw.fit_domain_min_doubleSpinBox.value()
    #     lambda_max = self._mw.fit_domain_max_doubleSpinBox.value()
    #
    #     new_fit_domain = np.array([lambda_min, lambda_max])
    #
    #     self._spectrum_logic.set_fit_domain(new_fit_domain)
    #
    # def reset_fit_domain_all_data(self):
    #     """ Reset the fit domain to match the full data set.
    #     """
    #     self._spectrum_logic.set_fit_domain()
    #
    # def update_fit_domain(self, domain):
    #     """ Update the displayed fit domain to new values (set elsewhere).
    #     """
    #     self._mw.fit_domain_min_doubleSpinBox.setValue(domain[0])
    #     self._mw.fit_domain_max_doubleSpinBox.setValue(domain[1])
    #
    # def restore_default_view(self):
    #     """ Restore the arrangement of DockWidgets to the default
    #     """
    #     # Show any hidden dock widgets
    #     self._mw.spectrum_fit_dockWidget.show()
    #
    #     # re-dock any floating dock widgets
    #     self._mw.spectrum_fit_dockWidget.setFloating(False)
    #
    #     # Arrange docks widgets
    #     self._mw.addDockWidget(QtCore.Qt.DockWidgetArea(QtCore.Qt.TopDockWidgetArea),
    #                            self._mw.spectrum_fit_dockWidget
    #                            )
    #
    #     # Set the toolbar to its initial top area
    #     self._mw.addToolBar(QtCore.Qt.TopToolBarArea,
    #                         self._mw.measure_ToolBar)
    #     self._mw.addToolBar(QtCore.Qt.TopToolBarArea,
    #                         self._mw.background_ToolBar)
    #     self._mw.addToolBar(QtCore.Qt.TopToolBarArea,
    #                         self._mw.differential_ToolBar)
    #     return 0

    #wavemeter gui did not use QtCore.Slots (??)

    def update_calculated_scan_params(self):
        finerates = [20, 10, 5, 2, 1, .5, .2, .1, .05, .02, .01, .005, .002, .001] #in GHz/s #TODO: Move?
        mediumrates = [100, 50, 20, 15, 10, 5, 2, 1] #in GHz/s #TODO: Move?
        speed_c = 299792458 #speed of light in m/s

        if self._mw.scanType_comboBox.currentText() == 'Fine':
            scanrate = finerates[int(self._mw.scanRate_comboBox.currentText())]* 10**9 #in Hz/s
        else:
            #TODO error handling if index is too high for medium
            scanrate = mediumrates[int(self._mw.scanRate_comboBox.currentText())]*10**9 #in Hz/s


        startWvln = self._mw.startWvln_doubleSpinBox.value() * 10**-9 #in m
        stopWvln = self._mw.stopWvln_doubleSpinBox.value()*10**-9 #in m
        midWvln = (stopWvln + startWvln)/2 #in m
        rangeWvln = (stopWvln - startWvln) #in m

        startFreq = speed_c/ stopWvln #in Hz
        stopFreq = speed_c/ startWvln #in Hz
        midFreq = (stopFreq + startFreq)/2 #in Hz
        rangeFreq = stopFreq - startFreq #in Hz
        scanrate_wvln = scanrate * speed_c/(midFreq**2) #in m/s


        self._mw.calcDwellTime_disp.setText('Hi') #Dwell time is related to how the counts get plotted. It is not
                                                #a property of the laser, but gets used for interpreting counts
        self._mw.calcScanRes_disp.setText("{0:.3f} GHz/s \n{1:.3f} pm/s".format(scanrate*10**-9,scanrate_wvln*10**12))
        totaltime = rangeFreq/scanrate
        self._mw.calcTotalTime_disp.setText("{0:.0f} min, {1:.0f} sec".format(totaltime//60,totaltime%60))


    #from laser.py gui
    @QtCore.Slot()
    def updateGui(self):
        """ Update labels, the plot and button states with new data. """
        #self._mw.currentLabel.setText(
        #    '{0:6.3f} {1}'.format(
        #        self._laser_logic.laser_current,
        #        self._laser_logic.laser_current_unit))
        #self._mw.powerLabel.setText('{0:6.3f} W'.format(self._laser_logic.laser_power))
        #self._mw.extraLabel.setText(self._laser_logic.laser_extra)

        #TODO throw error if startwavelength > stopwavlength
        #OR? do this in update_calcualated_scan_params???
        #TODO don't throw an error, but just don't allow the action to occur (eg don't update gui and laser to reflect it)

        self._mw.wvlnRead_disp.setText("{0:.5f}".format(self._laser_logic.current_wavelength))
#        self.updateButtonsEnabled()

      #  print('inside updateGui')
     #   print(self._laser_logic.current_wavelength)

        #TODO use for plot?
        #for name, curve in self.curves.items():
        #    curve.setData(x=self._laser_logic.data['time'], y=self._laser_logic.data[name])
