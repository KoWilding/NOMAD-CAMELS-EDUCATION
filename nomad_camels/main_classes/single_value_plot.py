import logging
import numpy as np

from bluesky.callbacks.core import CallbackBase

from PySide6.QtWidgets import QWidget, QGridLayout, QLabel
from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtGui import QIcon, QFont

from nomad_camels.bluesky_handling.evaluation_helper import Evaluator

from nomad_camels.utility.plot_placement import place_widget
from importlib import resources
from nomad_camels import graphics

from PySide6.QtCore import Signal as pySignal


class single_value_plot(QWidget):
    """A widget that displays a single evaluated value in large text."""

    closing = pySignal()
    reopened = pySignal()

    def __init__(
        self,
        value,
        *,
        epoch="run",
        namespace=None,
        title="",
        stream_name="primary",
        parent=None,
        font_size=48,
        unit="",
        top_left_x=None,
        top_left_y=None,
        plot_width=None,
        plot_height=None,
        **kwargs,
    ):
        super().__init__(parent=parent)
        self.name_label = QLabel(title)  # voher value
        self.name_label.setAlignment(Qt.AlignCenter)
        name_font = QFont()
        name_font.setPointSize(max(int(font_size * 0.8), 8))  # voher 0.3
        name_font.setBold(True)
        self.name_label.setFont(name_font)

        self.value_label = QLabel(str(np.nan))
        self.value_label.setAlignment(Qt.AlignCenter)
        value_font = QFont()
        value_font.setPointSize(font_size)
        value_font.setBold(True)
        self.value_label.setFont(value_font)

        self.livePlot = Live_Value(
            value,
            epoch=epoch,
            namespace=namespace,
            stream_name=stream_name,
            parent=self,
            value_label=self.value_label,
            unit=unit,
            **kwargs,
        )
        self.livePlot.new_data.connect(self.show_again)

        layout = QGridLayout()
        layout.addWidget(self.name_label, 0, 0)
        layout.addWidget(self.value_label, 1, 0)
        self.setLayout(layout)

        if title:
            self.setWindowTitle(title)
        else:
            self.setWindowTitle(value)
        self.setWindowIcon(
            QIcon(str(resources.files(graphics) / "CAMELS_Icon.png")))
        self.stream_name = stream_name
        place_widget(self, top_left_x, top_left_y, plot_width, plot_height)

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


class Teleporter(QObject):
    name_doc_escape = pySignal(str, dict, object)


def handle_teleport(name, doc, obj):
    obj(name, doc, escape=True)


class Live_Value(QObject, CallbackBase):
    """Evaluates a single value/expression on every event and pushes it
    into the given QLabel."""

    new_data = pySignal()

    def __init__(
        self,
        value,
        value_label,
        *,
        epoch="run",
        namespace=None,
        stream_name="primary",
        parent=None,
        unit="",
        **kwargs,
    ):
        CallbackBase.__init__(self)
        QObject.__init__(self)
        self.__teleporter = Teleporter()
        self.__teleporter.name_doc_escape.connect(handle_teleport)
        self.value = value
        self.stream_name = stream_name
        self.value_label = value_label
        self.unit = unit
        self.eva = Evaluator(namespace=namespace)
        self.multi_stream = kwargs.get("multi_stream", False)

        self.desc = []
        self.epoch_offset = 0
        self.epoch = epoch

    def descriptor(self, doc):
        if doc["name"] == self.stream_name:
            self.desc.append(doc["uid"])
        elif (
            self.multi_stream
            and doc["name"].startswith(self.stream_name)
            and not doc["name"][len(self.stream_name):].startswith(
                "||subprotocol_stream||"
            )
        ):
            self.desc.append(doc["uid"])

    def start(self, doc):
        self.epoch_offset = doc["time"]
        super().start(doc)
        self.eva.start(doc)

    def event(self, doc):
        if isinstance(doc, QEvent):
            return QWidget.event(self, doc)
        if doc["descriptor"] not in self.desc:
            return

        if self.value == "time":
            new_val = doc["time"]
            if self.epoch == "run":
                new_val -= self.epoch_offset
        else:
            try:
                new_val = doc["data"][self.value]
            except KeyError:
                if not self.eva.is_to_date(doc["time"]):
                    self.eva.event(doc)
                try:
                    new_val = self.eva.eval(self.value)
                except ValueError:
                    new_val = np.nan
                    logging.error(
                        f'Could not evaluate value "{self.value}" in Single Value Plot.'
                    )

        if isinstance(new_val, (int, float)):
            text = f"{new_val:.4g}"
        else:
            text = str(new_val)
        if self.unit:
            text = f"{text} {self.unit}"
        self.value_label.setText(text)
        self.new_data.emit()

    def __call__(self, name, doc, *, escape=False):
        if not escape and self.__teleporter is not None:
            self.__teleporter.name_doc_escape.emit(name, doc, self)
        else:
            return CallbackBase.__call__(self, name, doc)
