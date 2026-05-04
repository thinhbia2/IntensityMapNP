import nidaqmx
import time
import numpy as np
from nidaqmx.constants import Edge
from nidaqmx.system import System

system = System.local()

for device in system.devices:
    print(f"Device: {device.name}")
    print(f"  Counters: {device.ci_physical_chans.channel_names}")

# Replace 'cDAQ1Mod1' with your module name and 'ai0' with the channel
# Device name can be found in NI Measurement & Automation Explorer (MAX)

COUNTER_CHANNEL = "cDAQ1Mod1/ctr0"

with nidaqmx.Task() as task:
    # Create a counter input channel for edge counting
    task.ci_channels.add_ci_count_edges_chan(
        counter=COUNTER_CHANNEL,
        edge=Edge.RISING,      # Count rising edges
        initial_count=0
    )

    # Start the task
    task.start()

    print("Counting rising edges... Press Ctrl+C to stop.")

    try:
        while True:
            count = task.read()   # Read current count
            print(f"Current count: {count}")
            time.sleep(1)

    except KeyboardInterrupt:
        print("Stopped.")
       
        
#import nidaqmx
#from nidaqmx.constants import Edge
#
#with nidaqmx.Task() as task:
#    chan = task.ci_channels.add_ci_count_edges_chan("cDAQ1Mod1/ctr0")
#
#    # Specify the counter timebase source:
#    #chan.ci_ctr_timebase_src = "/cDAQ9170/20MHzTimebase"
#    chan.ci_ctr_timebase_rate = 20_000_000  # Set the nominal rate
#
#    chan.ci_count_edges_active_edge = Edge.RISING
#
#    task.start()
#    count = task.read()
#    print("Count:", count)