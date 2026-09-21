import logging
import numpy as np

from bluesky.callbacks.core import CallbackBase

from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, QEvent, QObject, QRectF, QPointF
from PySide6.QtGui import QIcon, QFont, QPainter, QPolygonF, QColor

from nomad_camels.bluesky_handling.evaluation_helper import Evaluator
from nomad_camels.utility.plot_placement import place_widget
from importlib import resources
from nomad_camels import graphics

from PySide6.QtCore import Signal as pySignal


def _nice_number(value, round_result=False):
    """Return a round number close to value (used for tick spacing)."""
    if value <= 0:
        return 1
    exponent = np.floor(np.log10(value))
    fraction = value / 10**exponent
    if round_result:
        if fraction < 1.5:
            nice_fraction = 1
        elif fraction < 3:
            nice_fraction = 2
        elif fraction < 7:
            nice_fraction = 5
        else:
            nice_fraction = 10
    else:
        if fraction <= 1:
            nice_fraction = 1
        elif fraction <= 2:
            nice_fraction = 2
        elif fraction <= 5:
            nice_fraction = 5
        else:
            nice_fraction = 10
    return nice_fraction * 10**exponent


def _nice_ticks(min_val, max_val, n_ticks=5):
    """Compute tick positions and rounded axis bounds."""
    if min_val == max_val:
        min_val -= 1
        max_val += 1
    axis_range = _nice_number(max_val - min_val, False)
    step = _nice_number(axis_range / max(n_ticks - 1, 1), True)
    nice_min = np.floor(min_val / step) * step
    nice_max = np.ceil(max_val / step) * step
    ticks = list(np.arange(nice_min, nice_max + step * 0.5, step))
    return ticks, nice_min, nice_max, step


def _minor_divisions(step):
    if step == 0.2:
        return 5

    if step == 0.5:
        return 4

    if np.isclose(step, 4):
        return 8       # 0.5

    if np.isclose(step, 3):
        return 6       # 0.5
    if (step > 5):
        exponent = np.floor(np.log10(step))
        fraction = step / 10**exponent

        if np.isclose(fraction, 1):
            return 10      # 1 -> 0.1
        elif np.isclose(fraction, 2):
            return 2       # 2 -> 1
        elif np.isclose(fraction, 5):
            return 5     # 5 -> 1

    return 2  # default 0.5 schritte


class Scale_Widget(QWidget):
    """Draws a horizontal scale with tick marks and a triangular marker for
    the current value. Automatically extends its range to fit seen values,
    unless manual min/max are given."""

    def __init__(self, parent=None, min_value=None, max_value=None, step=None):
        super().__init__(parent=parent)
        self.manual_min = min_value
        self.manual_max = max_value
        self.manual_step = step
        self.seen_min = min_value if min_value is not None else 0.0
        self.seen_max = max_value if max_value is not None else 1.0
        self.value = None
        self.setMinimumHeight(70)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def update_value(self, value):
        if value is None or not isinstance(value, (int, float)) or np.isnan(value):
            return
        self.value = value
        if self.manual_min is None:
            self.seen_min = min(self.seen_min, value)
        if self.manual_max is None:
            self.seen_max = max(self.seen_max, value)
        self.update()

    def get_bounds(self):
        min_val = self.manual_min if self.manual_min is not None else self.seen_min
        max_val = self.manual_max if self.manual_max is not None else self.seen_max
        if min_val == max_val:
            max_val = min_val + 1
        return min_val, max_val

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 25
        line_y = h * 0.4
        x0, x1 = margin, w - margin

        min_val, max_val = self.get_bounds()

        if self.manual_step:
            step = self.manual_step
            nice_min = np.floor(min_val / step) * step
            nice_max = np.ceil(max_val / step) * step
            ticks = list(np.arange(nice_min, nice_max + step * 0.5, step))
        else:
            ticks, nice_min, nice_max, step = _nice_ticks(min_val, max_val)

        if nice_max == nice_min:
            nice_max = nice_min + 1

        def to_x(val):
            frac = (val - nice_min) / (nice_max - nice_min)
            return x0 + frac * (x1 - x0)

        painter.setPen(QColor("black"))
        painter.drawLine(QPointF(x0, line_y), QPointF(x1, line_y))

        font = QFont()

        font.setPointSize(9)
        painter.setFont(font)

        minor_divisions = _minor_divisions(step)

        for i in range(len(ticks) - 1):
            start = ticks[i]
            end = ticks[i + 1]

            for j in range(1, minor_divisions):
                minor_tick = start + (end - start) * j / minor_divisions

                if minor_tick < nice_min - 1e-9 or minor_tick > nice_max + 1e-9:
                    continue

                tx = to_x(minor_tick)

                painter.drawLine(
                    QPointF(tx, line_y - 3),
                    QPointF(tx, line_y + 3),
                )

        for tick in ticks:
            if tick < nice_min - 1e-9 or tick > nice_max + 1e-9:
                continue

            tx = to_x(tick)

            painter.drawLine(
                QPointF(tx, line_y - 6),
                QPointF(tx, line_y + 6),
            )

            painter.drawText(
                QRectF(tx - 30, line_y + 8, 60, 20),
                Qt.AlignHCenter | Qt.AlignTop,
                f"{tick:g}",
            )

        # marker: red triangle pointing up into the value's position on the line
        if self.value is not None and not np.isnan(self.value):
            clamped = min(max(self.value, nice_min), nice_max)
            vx = to_x(clamped)
            size = 8
            triangle = QPolygonF(
                [
                    QPointF(vx, line_y),
                    QPointF(vx - size, line_y + size * 1.6),
                    QPointF(vx + size, line_y + size * 1.6),
                ]
            )
            painter.setBrush(QColor("red"))
            painter.setPen(QColor("red"))
            painter.drawPolygon(triangle)


class Gauge_Plot(QWidget):
    """A widget displaying a value as a marker position on a horizontal scale."""

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
        unit="",
        min_value=None,
        max_value=None,
        step=None,
        title_font_size=None,
        top_left_x=None,
        top_left_y=None,
        plot_width=None,
        plot_height=None,
        **kwargs,
    ):
        super().__init__(parent=parent)
        self.name_label = QLabel(title or value)
        self.name_label.setAlignment(Qt.AlignCenter)
        name_font = QFont()
        name_font.setPointSize(title_font_size or 14)
        self.name_label.setFont(name_font)

        self.value_label = QLabel(str(np.nan))
        self.value_label.setAlignment(Qt.AlignCenter)
        value_font = QFont()
        value_font.setPointSize((title_font_size or 14) + 4)
        value_font.setBold(True)
        self.value_label.setFont(value_font)

        self.scale_widget = Scale_Widget(
            self, min_value=min_value, max_value=max_value, step=step
        )

        self.livePlot = Live_Gauge(
            value,
            epoch=epoch,
            namespace=namespace,
            stream_name=stream_name,
            parent=self,
            scale_widget=self.scale_widget,
            value_label=self.value_label,
            unit=unit,
            **kwargs,
        )
        self.livePlot.new_data.connect(self.show_again)

        layout = QGridLayout()
        layout.addWidget(self.name_label, 0, 0)
        layout.addWidget(self.value_label, 1, 0)
        layout.addWidget(self.scale_widget, 2, 0)
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


class Live_Gauge(QObject, CallbackBase):
    """Evaluates the value on every event and updates the scale widget/label."""

    new_data = pySignal()

    def __init__(
        self,
        value,
        scale_widget,
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
        self.scale_widget = scale_widget
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
                        f'Could not evaluate value "{self.value}" in Gauge Plot.'
                    )

        if isinstance(new_val, (int, float)):
            text = f"{new_val:.4g}"
            self.scale_widget.update_value(new_val)
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
