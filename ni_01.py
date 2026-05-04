# SPCM-AQRH Real-Time APD Counter GUI
# Install:
# pip install nidaqmx pyqtgraph PyQt5 numpy

import sys
import time
import csv
import numpy as np

import nidaqmx
from nidaqmx.constants import Edge
from nidaqmx.system import System

from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg


class SPCMAQRHGui(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SPCM-AQRH APD Counter GUI")

        self.counter_task = None
        self.gate_task = None

        self.running = False
        self.recording = False

        self.last_count = 0
        self.start_time = None
        self.data = []

        self.init_ui()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_counts)

    def init_ui(self):
        layout = QtWidgets.QGridLayout(self)

        self.device_box = QtWidgets.QTextEdit()
        self.device_box.setReadOnly(True)
        self.device_box.setMaximumHeight(120)

        self.counter_channel = QtWidgets.QLineEdit("cDAQ1Mod1/ctr0")
        self.gate_channel = QtWidgets.QLineEdit("cDAQ1Mod1/port0/line0")

        self.bin_time = QtWidgets.QDoubleSpinBox()
        self.bin_time.setRange(0.001, 10.0)
        self.bin_time.setValue(1.0)
        self.bin_time.setSuffix(" s")

        self.window_time = QtWidgets.QDoubleSpinBox()
        self.window_time.setRange(1, 3600)
        self.window_time.setValue(60)
        self.window_time.setSuffix(" s")

        self.use_gate = QtWidgets.QCheckBox("Use gate control")
        self.use_gate.setChecked(False)

        self.scan_button = QtWidgets.QPushButton("Scan NI Devices")
        self.connect_button = QtWidgets.QPushButton("Connect")
        self.disconnect_button = QtWidgets.QPushButton("Disconnect")
        self.record_button = QtWidgets.QPushButton("Start Record")
        self.save_button = QtWidgets.QPushButton("Save CSV")

        self.count_label = QtWidgets.QLabel("Counts/bin: 0")
        self.rate_label = QtWidgets.QLabel("Rate: 0 cps")
        self.status_label = QtWidgets.QLabel("Status: Disconnected")

        self.plot = pg.PlotWidget()
        self.plot.setBackground("k")
        self.plot.setLabel("left", "Counts per bin")
        self.plot.setLabel("bottom", "Time", units="s")
        self.curve = self.plot.plot([], [], pen="y")

        layout.addWidget(QtWidgets.QLabel("Available NI devices:"), 0, 0, 1, 2)
        layout.addWidget(self.device_box, 1, 0, 1, 2)

        layout.addWidget(QtWidgets.QLabel("Counter channel:"), 2, 0)
        layout.addWidget(self.counter_channel, 2, 1)

        layout.addWidget(QtWidgets.QLabel("Gate channel:"), 3, 0)
        layout.addWidget(self.gate_channel, 3, 1)

        layout.addWidget(QtWidgets.QLabel("Bin time:"), 4, 0)
        layout.addWidget(self.bin_time, 4, 1)

        layout.addWidget(QtWidgets.QLabel("Window time:"), 5, 0)
        layout.addWidget(self.window_time, 5, 1)

        layout.addWidget(self.use_gate, 6, 0, 1, 2)

        layout.addWidget(self.scan_button, 7, 0)
        layout.addWidget(self.connect_button, 7, 1)

        layout.addWidget(self.disconnect_button, 8, 0)
        layout.addWidget(self.record_button, 8, 1)

        layout.addWidget(self.save_button, 9, 0, 1, 2)

        layout.addWidget(self.count_label, 10, 0)
        layout.addWidget(self.rate_label, 10, 1)

        layout.addWidget(self.status_label, 11, 0, 1, 2)
        layout.addWidget(self.plot, 12, 0, 1, 2)

        self.scan_button.clicked.connect(self.scan_devices)
        self.connect_button.clicked.connect(self.connect_spcm)
        self.disconnect_button.clicked.connect(self.disconnect_spcm)
        self.record_button.clicked.connect(self.toggle_record)
        self.save_button.clicked.connect(self.save_csv)

    def scan_devices(self):
        try:
            system = System.local()
            text = ""

            for device in system.devices:
                text += f"Device: {device.name}\n"
                text += f"  Counters: {device.ci_physical_chans.channel_names}\n"
                text += f"  Digital lines: {device.do_lines.channel_names}\n\n"

            self.device_box.setText(text)

        except Exception as e:
            self.device_box.setText(f"Error scanning devices:\n{e}")

    def connect_spcm(self):
        try:
            counter = self.counter_channel.text().strip()

            self.counter_task = nidaqmx.Task()

            self.counter_task.ci_channels.add_ci_count_edges_chan(
                counter=counter,
                edge=Edge.RISING,
                initial_count=0
            )

            if self.use_gate.isChecked():
                gate = self.gate_channel.text().strip()

                self.gate_task = nidaqmx.Task()
                self.gate_task.do_channels.add_do_chan(gate)

                self.gate_task.write(True)

            self.counter_task.start()

            self.last_count = self.counter_task.read()
            self.start_time = time.time()
            self.data = []

            self.running = True

            interval_ms = int(self.bin_time.value() * 1000)
            self.timer.start(interval_ms)

            self.status_label.setText("Status: Connected and counting")

        except Exception as e:
            self.status_label.setText(f"Connection error: {e}")

    def disconnect_spcm(self):
        self.running = False
        self.timer.stop()

        try:
            if self.gate_task is not None:
                self.gate_task.write(False)
                self.gate_task.close()
                self.gate_task = None

            if self.counter_task is not None:
                self.counter_task.stop()
                self.counter_task.close()
                self.counter_task = None

            self.status_label.setText("Status: Disconnected")

        except Exception as e:
            self.status_label.setText(f"Disconnect error: {e}")

    def update_counts(self):
        if not self.running or self.counter_task is None:
            return

        try:
            current_count = self.counter_task.read()

            counts_bin = current_count - self.last_count
            self.last_count = current_count

            t = time.time() - self.start_time
            bin_s = self.bin_time.value()
            cps = counts_bin / bin_s

            if self.recording:
                self.data.append([t, counts_bin, cps])

            self.count_label.setText(f"Counts/bin: {counts_bin}")
            self.rate_label.setText(f"Rate: {cps:.2f} cps")

            plot_data = self.data.copy()

            if not self.recording:
                plot_data.append([t, counts_bin, cps])

            if len(plot_data) > 0:
                arr = np.array(plot_data)

                window = self.window_time.value()
                arr = arr[arr[:, 0] >= max(0, t - window)]

                self.curve.setData(arr[:, 0], arr[:, 1])

        except Exception as e:
            self.status_label.setText(f"Read error: {e}")

    def toggle_record(self):
        if not self.running:
            self.status_label.setText("Connect first before recording")
            return

        self.recording = not self.recording

        if self.recording:
            self.data = []
            self.record_button.setText("Stop Record")
            self.status_label.setText("Recording started")
        else:
            self.record_button.setText("Start Record")
            self.status_label.setText("Recording stopped")

    def save_csv(self):
        if len(self.data) == 0:
            self.status_label.setText("No recorded data to save")
            return

        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save APD Counts",
            "spcm_aqrh_counts.csv",
            "CSV Files (*.csv)"
        )

        if filename:
            with open(filename, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["time_s", "counts_per_bin", "counts_per_second"])
                writer.writerows(self.data)

            self.status_label.setText(f"Saved: {filename}")

    def closeEvent(self, event):
        self.disconnect_spcm()
        event.accept()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    window = SPCMAQRHGui()
    window.resize(900, 700)
    window.show()

    sys.exit(app.exec_())