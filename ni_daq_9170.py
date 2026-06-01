import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
import threading
import time
import csv
import numpy as np
import nidaqmx
from nidaqmx.constants import Edge
from nidaqmx.system import System
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import FuncFormatter

class NICounterTimeTrace:
    def __init__(self, parent, main_gui):
        self.main_gui = main_gui
        self.frame = ttk.Frame(parent)
        #self.root.title("NI Counter Time Trace")
        #self.root.geometry("1400x400")

        self.running = False
        self.task = None
        # =========================
        # Fonts and styles
        # =========================
        self.arr18 = ('Arial', 18)

        self.style = ttk.Style()
        self.style.configure('TLabel', font=self.arr18)
        self.style.configure('TButton', font=self.arr18)
        self.style.configure('TEntry', font=self.arr18)
        self.style.configure('TCombobox', font=self.arr18)

        # =========================
        # Data storage
        # =========================
        self.over_flow = 2**32
        self.current_cps = 0                            
        self.times = []
        self.count_rates = []
        self.recording = False
        self.saved_data = []
        self.record_start_time = None

        # =========================
        # Top control frame
        # =========================
        control_frame = ttk.Frame(parent)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        control_frame = self.frame
        control_frame.grid(row=0,column=0,sticky="ew",padx=5,pady=0)

        # Detect NI devices
        self.system = System.local()
        self.counter_channels = []

        for device in self.system.devices:
            for ch in device.ci_physical_chans.channel_names:
                self.counter_channels.append(ch)

        if not self.counter_channels:
            self.counter_channels = ["No NI Counter Found"]

        # Channel selector
        ttk.Label(control_frame, text="Channel:").grid(row=0, column=0, padx=5,pady=0)
        self.channel_combo = ttk.Combobox(control_frame,font=self.arr18,values=self.counter_channels,width=18)
        self.channel_combo.grid(row=0, column=1, padx=5, pady=0)
        self.channel_combo.current(0)

        # Sample interval
        ttk.Label(control_frame, text="Bin (s):").grid(row=0, column=2, padx=5, pady=0)
        self.interval_entry = ttk.Entry(control_frame, font=self.arr18, width=5)
        self.interval_entry.grid(row=0, column=3, padx=5, pady=0)
        self.interval_entry.insert(0, "0.1")

        # Window size
        ttk.Label(control_frame, text="Window (s):").grid(row=0, column=4, padx=5, pady=0)
        self.window_entry = ttk.Entry(control_frame, font=self.arr18, width=5)
        self.window_entry.grid(row=0, column=5, padx=5, pady=0)
        self.window_entry.insert(0, "10")

        ttk.Label(control_frame, text="Record (s):").grid(row=0, column=6, padx=5, pady=0)
        self.record_entry = ttk.Entry(control_frame, font=self.arr18, width=5)
        self.record_entry.grid(row=0, column=7, padx=5, pady=0)
        self.record_entry.insert(0, "60")

        # Current CPS label
        self.cps_label = ttk.Label(control_frame, text="Rate: --")
        self.cps_label.grid(row=0, column=8, padx=20, pady=0)

        # Start button
        self.start_button = tk.Button(control_frame,text="Start",bg="green",fg="white",width=6,font=self.arr18,command=self.toggle_measurement)
        self.start_button.grid(row=0, column=9, padx=10)

        # Record button
        self.record_button = tk.Button(
            control_frame,
            text="Record",
            bg="blue",
            fg="white",
            width=10,
            font=self.arr18,
            command=self.toggle_record
        )
        self.record_button.grid(row=0, column=10, padx=10)

        # =========================
        # Matplotlib Figure
        # =========================
        self.fig, self.ax = plt.subplots(figsize=(0.8, 1.6))
        self.fig.subplots_adjust(left=0.1,right=0.9,top=0.99,bottom=0.15)
        self.line, = self.ax.plot([], [], linewidth=1)

        #self.ax.set_title("NI Counter Time Trace", fontsize=10)
        self.ax.set_xlabel("Time (s)", fontsize=7)
        self.ax.xaxis.set_label_coords(1.02, -0.04)
        self.ax.set_ylabel("Rate (Cps)", fontsize=7)
        self.ax.yaxis.set_major_formatter(FuncFormatter(self.cps_axis_formatter))
        self.ax.tick_params(axis='both', labelsize=8)
        self.ax.grid(False)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.get_tk_widget().grid(row=1,column=0,columnspan=20,sticky="nsew",padx=5,pady=5)

    def close_task(self):       
        if self.task is None:
            return
        try:
            self.task.stop()
        except:
            pass

        try:
            self.task.close()
        except:
            pass
        self.task = None
    
    def initialize_counter(self):
        if self.task is not None:
            return

        counter_channel = self.channel_combo.get()
        self.task = nidaqmx.Task()
        self.task.ci_channels.add_ci_count_edges_chan(
            counter=counter_channel,
            edge=Edge.RISING,
            initial_count=0
        )

        self.task.start()
        self.previous_count = self.task.read()
        self.last_time = time.time()
        
    def measure_cps(self):
        self.initialize_counter()
        current_time = time.time()
        current_count = self.task.read()
        dt = current_time - self.last_time

        if dt <= 0:
            return 0, 0

        # Handle 32-bit rollover
        if current_count >= self.previous_count:
            delta_counts = current_count - self.previous_count
        else:
            delta_counts = (self.over_flow - self.previous_count) + current_count
        cps = delta_counts / dt
        self.previous_count = current_count
        self.last_time = current_time

        return cps, dt

    # =====================================================
    # Start / Stop
    # =====================================================
    def toggle_measurement(self):
        if not self.running:
            self.running = True
            self.previous_count = 0
            self.last_time = None
            self.start_button.config(text="Stop",bg="red")
            threading.Thread(target=self.measure_loop,daemon=True).start()

        else:
            self.running = False
            #self.previous_count = 0
            #self.last_time = None
            self.start_button.config(text="Start",bg="green")

    # =====================================================
    # Measurement loop
    # =====================================================
    def measure_loop(self):
        counter_channel = self.channel_combo.get()

        if counter_channel == "No NI Device Found":
            messagebox.showerror("Error", "No NI device detected")
            return

        sample_interval = float(self.interval_entry.get())
        window_size = float(self.window_entry.get())
        max_points = int(window_size / sample_interval)
        self.times = []
        self.count_rates = []

        try:
            self.initialize_counter()

            while self.running:
                #if self.main_gui.is_running:
                #    time.sleep(0.1)
                #    continue

                time.sleep(sample_interval)
                cps, dt = self.measure_cps()
                self.current_cps = cps                                      
                if len(self.times) == 0:
                    elapsed_time = 0
                else:
                    elapsed_time = self.times[-1] + dt

                self.times.append(elapsed_time)
                self.count_rates.append(cps)

                if self.recording:
                    record_elapsed = time.time() - self.record_start_time
                    self.saved_data.append([record_elapsed, cps])
                    record_limit = float(self.record_entry.get())
                    if record_elapsed >= record_limit:
                        self.stop_recording()
        
                if len(self.times) > max_points:
                    self.times.pop(0)
                    self.count_rates.pop(0)

                self.update_plot()
                self.cps_label.config(text=self.format_cps(cps))

        except Exception as e:
            messagebox.showerror("DAQ Error", str(e))

        finally:
            self.running = False
            #if self.recording:
            #    self.stop_recording()
            self.close_task()
            self.start_button.config(text="Start",bg="green")

    # =====================================================
    # Update plot
    # =====================================================
    def update_plot(self):

        self.line.set_data(self.times, self.count_rates)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()

    # =====================================================
    # Save data
    # =====================================================
    def save_recorded_data(self):

        if len(self.times) == 0:
            messagebox.showwarning("No Data", "No data available to save")
            return

        filename = filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV files", "*.csv")])

        if not filename:
            return

        with open(filename, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Time (s)", "Counts Per Second"])

            for row in self.saved_data:
                writer.writerow(row)
        # Save plot image
        plot_filename = filename.replace('.csv', '.png')
        self.fig.savefig(plot_filename, dpi=300)

        messagebox.showinfo("Saved","Data and plot saved successfully")

    def format_cps(self, cps):
        if cps >= 1e6:
            return f"{cps/1e6:.3g} Mcps"
        elif cps >= 1e3:
            return f"{cps/1e3:.3g} Kcps"
        else:
            return f"{cps:.0f} cps"
            
    def cps_axis_formatter(self, x, pos):
        if x >= 1e6:
            return f"{x/1e6:.1f}M"
        elif x >= 1e3:
            return f"{x/1e3:.1f}K"
        else:
            return f"{x:.0f}"
        
    def toggle_record(self):

        # Auto-start acquisition
        if not self.running:
            self.toggle_measurement()

        if not self.recording:
            self.recording = True
            self.saved_data = []
            self.record_start_time = time.time()
            self.record_button.config(text="Recording",bg="red")

        else:
            self.stop_recording()

    def stop_recording(self):
        self.recording = False
        self.record_button.config(text="Record",bg="blue")
        self.save_recorded_data()