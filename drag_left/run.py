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
import sys
import json
import scipy.stats
import matplotlib.pyplot as plt
if sys.version_info[0] == 2:
    input = raw_input

test_dur = 1.0    # Seconds
max_force = 500.0  # lbf
min_force = 0.0
steps = 2
device = "cDAQ1Mod2"
plot = True

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
    df["volts_per_volt"] = np.zeros(len(df.nominal_force))
    return df

def collect_data(phys_chan, duration):
    """Collects data from the specified channel for the duration."""
    print("\nCollecting data for {} seconds".format(duration))
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
    
def regress(applied_force, volts_per_volt):
    """Linearly regress applied force versus V/V"""
    results = scipy.stats.linregress(volts_per_volt, applied_force)
    slope, intercept, r_value, p_value, std_err = results
    return {"slope" : slope,
            "intercept" : intercept,
            "r_value" : r_value,
            "p_value" : p_value,
            "std_err" : std_err,
            "units" : "N/(V/V)"}
    
def save_raw_data(data_dict, index):
    folder = os.path.join("data", "raw", str(index))
    path = os.path.join(folder, "data.h5")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    ts.savehdf(path, data_dict.to_dict("list"), mode="w")
    print("Saved raw data to", path)
    
def save_metadata(metadata):
    with open("calibration.json", "w") as f:
        json.dump(metadata, f, indent=4)

def main():
    df = create_dataframe()
    metadata = {}
    metadata["side"] = get_side()
    metadata["9237 physical channel"] = get_physical_channel()
    for index, force in enumerate(df.nominal_force):
        print("\nSet the applied force to {} lbf".format(force))
        initial_force = float(input("What is the current applied force? "))
        df.initial_force[index] = initial_force
        rawdata = collect_data(metadata["9237 physical channel"], test_dur)
        save_raw_data(rawdata, index)
        df.volts_per_volt[index] = np.mean(rawdata["volts_per_volt"])
        print("Average measured voltage: {} V/V".format(df.volts_per_volt[index]))
        final_force = float(input("What is the current applied force? "))
        df.final_force[index] = final_force
    df["average_force_lbf"] = (df.initial_force + df.final_force)/2
    df["average_force_newtons"] = df.average_force_lbf*4.44822162
    print("\nCalibration complete")
    print("\nResults:\n")
    print(df)
    df.to_csv("data/processed.csv", index=False)
    regression = regress(df.average_force_newtons, df.volts_per_volt)
    print("\nRegression:")
    for k, v in regression.items():
        print(k, ":", v)
    metadata["linear regression"] = regression
    save_metadata(metadata)
    if plot:
        plt.style.use("ggplot")
        plt.figure()
        plt.plot(df.volts_per_volt, df.average_force_newtons, "ok", 
                 label="Measured")
        plt.xlabel("V/V")
        plt.ylabel("Applied force (N)")
        plt.plot(df.volts_per_volt, df.volts_per_volt*regression["slope"] \
                 + regression["intercept"], label="Lin. reg.")
        plt.legend(loc=2)
        plt.grid(True)
        plt.show()

if __name__ == "__main__":
    main()