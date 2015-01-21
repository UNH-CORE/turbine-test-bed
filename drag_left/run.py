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

side = "left"
test_dur = 1.0    # Seconds
sample_rate = 2000 # Hz
max_force = 500.0  # lbf
min_force = 0.0
steps_ascending = 2
steps_descending = 2
device = "cDAQ9188-16D66BBMod3"
phys_chan = "ai1"
plot = True
    
def create_dataframe(direction):
    df = pd.DataFrame()
    if direction == "ascending":
        df["nominal_force"] = np.linspace(min_force, max_force, steps_ascending)
    elif direction == "descending":
        df["nominal_force"] = np.linspace(max_force, min_force, steps_descending)
    df["initial_force"] = np.zeros(len(df.nominal_force))
    df["final_force"] = np.zeros(len(df.nominal_force))
    df["mean_volts_per_volt"] = np.zeros(len(df.nominal_force))
    df["std_volts_per_volt"] = np.zeros(len(df.nominal_force))
    return df

def collect_data(duration):
    """Collects data from the specified channel for the duration."""
    print("\nCollecting data for {} seconds".format(duration))
    c = daqmx.channels.AnalogInputBridgeChannel()
    c.physical_channel = "{}/{}".format(device, phys_chan)
    c.name = "volts_per_volt"
    task = daqmx.tasks.Task()
    task.add_channel(c)
    task.sample_rate = sample_rate
    task.setup_append_data()
    task.start()
    while len(task.data["time"]) < duration*sample_rate:
        time.sleep(0.2)
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
    
def save_raw_data(data_dict, index, direction):
    folder = os.path.join("data", "raw", direction, str(index))
    path = os.path.join(folder, "data.h5")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    ts.savehdf(path, data_dict.to_dict("list"), mode="w")
    print("Saved raw data to", path)
    
def save_metadata(metadata):
    with open("calibration.json", "w") as f:
        json.dump(metadata, f, indent=4)
        
def run_cal(direction):
    print("Running calibration", direction)
    df = create_dataframe(direction)
    for index, force in enumerate(df.nominal_force):
        print("\nSet the applied force to {} lbf".format(force))
        initial_force = float(input("What is the current applied force? "))
        df.initial_force[index] = initial_force
        rawdata = collect_data(test_dur)
        save_raw_data(rawdata, index, direction)
        df.mean_volts_per_volt[index] = np.mean(rawdata["volts_per_volt"])
        df.std_volts_per_volt[index] = np.std(rawdata["volts_per_volt"])
        print("Mean measured voltage: {} V/V".format(df.mean_volts_per_volt[index]))
        final_force = float(input("What is the current applied force? "))
        df.final_force[index] = final_force
    df["mean_force_lbf"] = (df.initial_force + df.final_force)/2
    df["mean_force_newtons"] = df.mean_force_lbf*4.44822162
    print("\n{} calibration complete".format(direction.title()))
    print("\nResults:\n")
    print(df)
    csv_folder = os.path.join("data", "processed")
    if not os.path.isdir(csv_folder):
        os.makedirs(csv_folder)
    csv_path = os.path.join(csv_folder, direction + ".csv")
    df.to_csv(csv_path, index=False)
    regression = regress(df.mean_force_newtons, df.mean_volts_per_volt)
    print("\n{} regression:".format(direction.title()))
    for k, v in regression.items():
        print(k, ":", v)
    return df, regression

def main():
    print("Calibrating {} drag slide\n".format(side))
    metadata = {}
    metadata["side"] = side
    metadata["9237 physical channel"] = phys_chan
    df_asc, reg_asc = run_cal("ascending")
    df_desc, reg_desc = run_cal("descending")
    metadata["linear regression ascending"] = reg_asc
    metadata["linear regression descending"] = reg_desc
    df_all = df_asc.append(df_desc)
    reg_all = regress(df_all.mean_force_newtons, df_all.mean_volts_per_volt)
    metadata["linear regression all"] = reg_all
    metadata["timestamp"] = time.asctime()
    save_metadata(metadata)
    if plot:
        plt.style.use("ggplot")
        plt.figure()
        plt.plot(df_asc.mean_volts_per_volt, df_asc.mean_force_newtons, "ok", 
                 label="Meas. asc.")
        plt.plot(df_desc.mean_volts_per_volt, df_desc.mean_force_newtons, "sb", 
                 label="Meas. desc.")
        plt.xlabel("V/V")
        plt.ylabel("Applied force (N)")
        plt.plot(df_all.mean_volts_per_volt, df_all.mean_volts_per_volt*reg_all["slope"] \
                 + reg_all["intercept"], label="Lin. reg. all")
        plt.legend(loc=2)
        plt.grid(True)
        plt.show()

if __name__ == "__main__":
    main()