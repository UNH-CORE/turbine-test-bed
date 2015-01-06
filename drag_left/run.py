#!/usr/bin/env python
"""
This module will run a calibration on the drag slides from 0 to 500 lbf.
"""
from __future__ import division, print_function
import pandas as pd
import numpy as np
from pxl import timeseries as ts
import time
import daqmx
import os

test_dur = 1.0    # Seconds
max_force = 500.0  # lbf
min_force = 0.0
steps = 2
device = "cDAQ1Mod2"

def get_side():
    """Asks the operator to input which side is being calibrated."""
    side = ""
    while not side.lower() in ["left", "right"]:
        side = input("Which side (left or right) is being calibrated? ")
    return side.lower()
    
def get_physical_channel():
    """Asks the operator which physical channel the load cell is connected to."""
    chan = ""
    while not chan in ["0", "1", "2", "3"]:
        chan = input("Which 9237 physical channel is the drag slide connected to? ")
    return chan
    
def create_dataframe():
    df = pd.DataFrame()
    df["nominal_force"] = np.linspace(min_force, max_force, steps)
    df["initial_force"] = np.zeros(len(df.nominal_force))
    df["final_force"] = np.zeros(len(df.nominal_force))
    df["meas_volts_per_volt"] = np.zeros(len(df.nominal_force))
    return df

def collect_data(phys_chan, duration):
    """Collects data from the specified channel for the duration."""
    print("Collecting data for {} seconds...".format(duration))
    c = daqmx.channels.AnalogInputBridgeChannel()
    c.physical_channel = "{}/ai{}".format(device, phys_chan)
    c.name = "volts_per_volt"
    task = daqmx.tasks.Task()
    task.add_channel(c)
    task.setup_append_data()
    task.start()
    time.sleep(duration)
    task.stop()
    task.clear()
    print("Data collection complete")
    return task.data
    
def process_data():
    """Takes raw voltage and computes mean value."""
    print("Processed data")
    
def save_raw_data(data_dict, index):
    folder = os.path.join("raw", str(index))
    if not os.path.isdir(folder):
        os.makedirs(folder)
    ts.savehdf(os.path.join(folder, "data.h5"), data_dict)
    print("Saved raw data")

def main():
    df = create_dataframe()
    metadata = {}
    metadata["side"] = get_side()
    metadata["physical channel"] = get_physical_channel()
    for index, force in enumerate(df.nominal_force):
        print("Set the applied force to {} lbf".format(force))
        df.initial_force[index] = float(input("What is the initial applied force? "))
        rawdata = collect_data(metadata["physical channel"], test_dur)
        save_raw_data(rawdata, index)
        df.meas_volts_per_volt[index] = np.mean(rawdata["volts_per_volt"])
        print("Average measured voltage: {} V/V".format(df.meas_volts_per_volt[index]))
        final_force = input("What is the final applied force? ")
        df.final_force[index] = float(final_force)
        # Compute averages for DataFrame
    print("Calibration complete")
    print("\nResults:\n")
    print(df)
    # Write DataFrame to CSV
    # Calculate slope and add to metadata
    # Write metadata

if __name__ == "__main__":
    main()