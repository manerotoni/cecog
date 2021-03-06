"""
imagedialog.py
"""

from __future__ import division

__author__ = 'rudolf.hoefler@gmail.com'
__copyright__ = ('The CellCognition Project'
                 'Copyright (c) 2006 - 2012'
                 'Gerlich Lab, IMBA Vienna, Austria'
                 'see AUTHORS.txt for contributions')
__licence__ = 'LGPL'
__url__ = 'www.cellcognition.org'


__all__ = ["ImageDialog"]


from PyQt4 import QtGui
from PyQt4 import QtCore
from PyQt4.QtCore import Qt

from qimage2ndarray import array2qimage

class ImageDialog(QtGui.QWidget):
    """Popup dialog to show classification and contour images."""

    def __init__(self, *args, **kw):
        super(ImageDialog, self).__init__(*args, **kw)
        self._images = None
        self.setWindowFlags(Qt.Window)

        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.graphics = QtGui.QLabel(self)
        self.graphics.setSizePolicy(
            QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                              QtGui.QSizePolicy.Expanding))
        self.graphics.setScaledContents(True)
        self.graphics.setMinimumSize(QtCore.QSize(100, 100))
        layout.addWidget(self.graphics)

        self.bottombar = QtGui.QFrame(self)
        self.bottombar.setLineWidth(0)
        bbar_layout = QtGui.QHBoxLayout(self.bottombar)
        bbar_layout.setContentsMargins(0, 0, 0, 0)

        self.combobox = QtGui.QComboBox(self.bottombar)
        self.combobox.setSizePolicy(
            QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                              QtGui.QSizePolicy.Fixed))

        bbar_layout.addStretch()
        bbar_layout.addWidget(self.combobox)
        bbar_layout.addStretch()
        bbar_layout.setSpacing(0)
        layout.addWidget(self.bottombar)

        self.combobox.activated[str].connect(self.setImage)

    def raise_(self):
        self.show()
        super(ImageDialog, self).raise_()

    def hasPixmap(self):
        if self.graphics.pixmap() is None:
            return False
        else:
            return True

    def setImage(self, name):
        assert isinstance(name, basestring)

        image = self._images[name]
        image = array2qimage(image.toArray(copy=False))
        pixmap = QtGui.QPixmap.fromImage(image)

        self.graphics.setPixmap(
            pixmap.scaled(self.size(), Qt.IgnoreAspectRatio,
                          Qt.SmoothTransformation))

    def clearImage(self):
        """Replace the current Image by a blank black image. If no
        image is set the method does nothing."""
        if self.hasPixmap():
            pix = self.graphics.pixmap()
            pix2 = QtGui.QPixmap(pix.size())
            pix2.fill(Qt.black)
            self.graphics.setPixmap(pix2)
            self.raise_()

    def updateImages(self, images, message):
        self.setWindowTitle(message)
        if self._images is None:
            image = images.values()[0]
            aspect = image.height/image.width
            self.resize(800, int(800*aspect))

        self._images = images
        current = self.combobox.currentText()
        self.combobox.clear()
        self.combobox.addItems(images.keys())

        if current in images.keys():
            self.combobox.setCurrentIndex(
                self.combobox.findText(current, Qt.MatchExactly))
        else:
            current = self.combobox.currentText()
            self.combobox.setCurrentIndex(0)

        if len(images) > 1:
            self.bottombar.show()
        else:
            self.bottombar.hide()
        self.setImage(current)
