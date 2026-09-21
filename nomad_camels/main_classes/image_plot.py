import os
import logging

from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont, QPixmap

from nomad_camels.utility.plot_placement import place_widget
from importlib import resources
from nomad_camels import graphics

from PySide6.QtCore import Signal as pySignal


class Image_Plot(QWidget):
    """A simple widget that displays a (PNG) image loaded from a given path."""

    closing = pySignal()
    reopened = pySignal()

    def __init__(
        self,
        image_path="",
        *,
        title="",
        parent=None,
        title_font_size=None,
        top_left_x=None,
        top_left_y=None,
        plot_width=None,
        plot_height=None,
        **kwargs,
    ):
        super().__init__(parent=parent)
        # Dummy callback so this widget can be subscribed to the Bluesky
        # dispatcher like every other plot type, even though it never
        # reacts to live data.
        self.livePlot = lambda name, doc: None
        self.image_path = image_path
        self._pixmap = None

        self.name_label = None
        if title:
            self.name_label = QLabel(title)
            self.name_label.setAlignment(Qt.AlignCenter)
            name_font = QFont()
            name_font.setPointSize(title_font_size or 14)
            self.name_label.setFont(name_font)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(1, 1)

        self._load_image()

        layout = QGridLayout()
        row = 0
        if self.name_label is not None:
            layout.addWidget(self.name_label, row, 0)
            row += 1
        layout.addWidget(self.image_label, row, 0)
        self.setLayout(layout)

        self.setWindowTitle(title or "Image Display")
        self.setWindowIcon(
            QIcon(str(resources.files(graphics) / "CAMELS_Icon.png")))
        place_widget(self, top_left_x, top_left_y, plot_width, plot_height)

    def _load_image(self):
        """(Re-)loads the pixmap from self.image_path and shows it."""
        if self.image_path and os.path.isfile(self.image_path):
            pixmap = QPixmap(self.image_path)
            if pixmap.isNull():
                logging.warning(
                    f'Could not load image "{self.image_path}" for Image plot.'
                )
                self._pixmap = None
                self.image_label.setText(
                    f'Could not load image:\n"{self.image_path}"'
                )
            else:
                self._pixmap = pixmap
                self._update_scaled_pixmap()
        else:
            self._pixmap = None
            self.image_label.setText(
                f'Image not found:\n"{self.image_path}"'
                if self.image_path
                else "No image path set"
            )

    def _update_scaled_pixmap(self):
        if self._pixmap is None:
            return
        scaled = self._pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def show_again(self):
        if not self.isVisible():
            self.show()
            self.reopened.emit()

    def clear_plot(self):
        pass

    def autoscale(self):
        pass

    def closeEvent(self, a0):
        self.closing.emit()
        super().closeEvent(a0)
