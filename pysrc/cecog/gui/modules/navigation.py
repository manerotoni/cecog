"""
                           The CellCognition Project
                     Copyright (c) 2006 - 2010 Michael Held
                      Gerlich Lab, ETH Zurich, Switzerland
                              www.cellcognition.org

              CellCognition is distributed under the LGPL License.
                        See trunk/LICENSE.txt for details.
                 See trunk/AUTHORS.txt for author contributions.
"""

__author__ = 'Michael Held'
__date__ = '$Date$'
__revision__ = '$Rev$'
__source__ = '$URL$'

__all__ = []

#-------------------------------------------------------------------------------
# standard library imports:
#
import time as time_lib

#-------------------------------------------------------------------------------
# extension module imports:
#
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4.Qt import *

import numpy

#-------------------------------------------------------------------------------
# cecog imports:
#
from cecog.gui.modules.module import Module
from cecog.util.util import yesno

#-------------------------------------------------------------------------------
# constants:
#

#-------------------------------------------------------------------------------
# functions:
#

#-------------------------------------------------------------------------------
# classes:
#

class NavigationModule(Module):

    NAME = 'Navigation'

    position_changed = pyqtSignal(str)
    time_changed = pyqtSignal(int)
    plate_changed = pyqtSignal(str)

    def __init__(self, parent, browser, meta_data):
        Module.__init__(self, parent, browser)

        self._meta_data = meta_data

        self._frame_info = QGroupBox('Plate Information', self)
        self.update_info_frame()

        splitter = QSplitter(Qt.Vertical, self)
        splitter.setMinimumWidth(40)

        layout = QBoxLayout(QBoxLayout.TopToBottom, self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.addWidget(splitter)

        grp1 = QGroupBox('Plates', splitter)
        grp2 = QGroupBox('Positions', splitter)
        splitter.addWidget(grp1)
        splitter.addWidget(grp2)

        layout = QGridLayout(grp1)
        layout.setContentsMargins(5, 10, 5, 5)

        table = QTableWidget(grp1)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        #table.setSizePolicy(QSizePolicy(QSizePolicy.Minimum,
        #                                QSizePolicy.Expanding))
        #table.setColumnCount(3)
        #table.setRowCount(len(meta_data.positions))
        #table.setMinimumWidth(20)
        layout.addWidget(table, 0, 0)

        layout = QGridLayout(grp2)
        layout.setContentsMargins(5, 10, 5, 5)

        table = QTableWidget(grp2)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setAlternatingRowColors(True)
        table.setStyleSheet('font-size: 10px;')

        column_names = ['Position']
        if self._meta_data.has_well_info:
            column_names += ['Well', 'Subwell']
        if self._meta_data.has_condition_info:
            column_names.append('Condition')
        if self._meta_data.has_timestamp_info:
            column_names.append('Time-lapse')

        table.setColumnCount(len(column_names))
        table.setHorizontalHeaderLabels(column_names)
        table.setRowCount(len(self._meta_data.positions))

        for idx, pos in enumerate(self._meta_data.positions):
            item = QTableWidgetItem(pos)
            item.setData(0, pos)
            table.setItem(idx, 0, item)

            if 'Time-lapse' in column_names:
                column = column_names.index('Time-lapse')
                info = self._meta_data.get_timestamp_info(pos)
                info_str = '%.1fmin (%.1fs)' % (info[0] / 60, info[1])
                table.setItem(idx, column, QTableWidgetItem(info_str))

        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.currentItemChanged.connect(self._on_position_changed)
        self._table_position = table
        #table.setMinimumWidth(20)
        layout.addWidget(table, 0, 0)

        if meta_data.has_timelapse:
            grp3 = QGroupBox('Time', splitter)
            splitter.addWidget(grp3)

            layout = QGridLayout(grp3)
            layout.setContentsMargins(5, 10, 5, 5)

            table = QTableWidget(grp3)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setSelectionMode(QTableWidget.SingleSelection)
            table.setSelectionBehavior(QTableWidget.SelectRows)
            table.setAlternatingRowColors(True)
            table.setStyleSheet('font-size: 10px;')

            column_names = ['Frame']
            if self._meta_data.has_timestamp_info:
                column_names += ['rel. t (min)', 'abs. t (GMT)']
            table.setColumnCount(len(column_names))
            table.setHorizontalHeaderLabels(column_names)
            table.setRowCount(len(self._meta_data.times))

            self._table_time = table
            self._table_time_column_names = column_names
            self.update_time_table()

            table.currentItemChanged.connect(self._on_time_changed)
            layout.addWidget(table, 0, 0)

        splitter.addWidget(self._frame_info)

    def update_time_table(self):
        table = self._table_time
        column_names = self._table_time_column_names
        plateid, position, dummy = self.browser.get_coordinates()
        for idx, time in enumerate(self._meta_data.times):
            item = QTableWidgetItem(str(time))
            item.setData(0, time)
            table.setItem(idx, 0, item)

            if self._meta_data.has_timestamp_info:
                ts_rel = self._meta_data.get_timestamp_relative(position, time)
                ts_abs = self._meta_data.get_timestamp_absolute(position, time)
                if not numpy.isnan(ts_rel):
                    info = '%.1f' % (ts_rel / 60)
                    table.setItem(idx, 1, QTableWidgetItem(info))
                if not numpy.isnan(ts_abs):
                    info = time_lib.strftime("%Y-%m-%d %H:%M:%S",
                                             time_lib.gmtime(ts_abs))
                    table.setItem(idx, 2, QTableWidgetItem(info))
        table.resizeColumnsToContents()
        table.resizeRowsToContents()

    def update_info_frame(self):
        frame = self._frame_info
        frame.setStyleSheet('QLabel { font-size: 10px }')
        meta = self._meta_data
        layout = QGridLayout(frame)
        txt  = '<table>' \
               '<tr><td align="right">Positions: </td><td>%d</td></tr>' % \
               meta.dim_p
        if meta.has_timelapse:
            txt += \
               '<tr><td align="right">Frames: </td><td>%d</td></tr>' % \
               meta.dim_t
        txt += '<tr><td align="right">Channels: </td><td>%d (%s)</td></tr>' \
               '<tr><td align="right">Z-slices: </td><td>%d</td></tr>' \
               '<tr><td align="right">Width / Height: </td><td>%d x %d</td></tr>' \
               '<tr><td colspan="2"></td></tr>' \
               '<tr><td align="right">Image Files: </td><td>%d</td></tr>' %\
               (meta.dim_c, meta.pixel_info, meta.dim_z, meta.dim_x,
                meta.dim_y, meta.image_files)
        txt += '<tr><td></td></tr>'
        if meta.has_timestamp_info:
            info = meta.plate_timestamp_info
            txt += \
               '<tr><td align="right">Time-lapse: </td><td>%.1f min (+/- %.1f s)</td></tr>' % \
               (info[0]/60, info[1])
        else:
            txt += '<tr><td align="right">Time-lapse info: </td><td>no</td></tr>'

        txt += '<tr><td align="right">Well info: </td><td>%s</td></tr>' % \
               yesno(meta.has_well_info)
        txt += '<tr><td align="right">Condition info: </td><td>%s</td></tr>' % \
               yesno(meta.has_condition_info)
        txt += '</table>'
        label = QLabel(txt, frame)
        layout.addWidget(label, 0, 0, 0, 0, Qt.AlignCenter | Qt.AlignHCenter)


    def initialize(self):
        self.browser.coordinates_changed.connect(self._on_coordinates_changed)

        self.position_changed.connect(self.browser.on_position_changed)
        self.time_changed.connect(self.browser.on_time_changed)
        plate, position, time = self.browser.get_coordinates()
        self._set_position(position)
        self._set_time(time)

    def _on_position_changed(self, current, previous):
        item = self._table_position.item(current.row(), 0)
        position = item.data(0).toPyObject()
        if self._meta_data.has_timelapse:
            self.update_time_table()
        self.position_changed.emit(position)

    def _on_time_changed(self, current, previous):
        item = self._table_time.item(current.row(), 0)
        time = int(item.data(0).toPyObject())
        self.time_changed.emit(time)

    def _on_coordinates_changed(self, plateid, position, time):
        self._set_position(position)
        self._set_time(time)

    def _set_position(self, position):
        self._table_position.blockSignals(True)
        item = self._table_position.findItems(position, Qt.MatchExactly)[0]
        self._table_position.setCurrentItem(item)
        self._table_position.blockSignals(False)

    def _set_time(self, time):
        if self._meta_data.has_timelapse:
            self._table_time.blockSignals(True)
            item = self._table_time.findItems(str(time), Qt.MatchExactly)[0]
            self._table_time.setCurrentItem(item)
            self._table_time.blockSignals(False)