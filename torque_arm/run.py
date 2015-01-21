#!/usr/bin/env python
"""
This script will run a calibration on the torque arm.
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

test_dur = 30.0    # seconds
sample_rate = 2000 # Hz
max_torque = 360.0  # Nm
min_torque = 0.0
steps_ascending = 10
steps_descending = 10
device = "cDAQ9188-16D66BBMod3"
phys_chan = "ai0"
plot = True
cal_length = 0.2032 # length of calibration arm in meters

def nm_to_lbf(nm):
    """Returns the equivalent pound force reading on the load cell for a
    specified torque value in Newton meters."""
    newtons = nm/cal_length
    return newtons*0.224808943

def lbf_to_nm(lbf):
    """Returns the equivalent torque reading in Newton meters for an applied
    load in pound force."""
    newtons = lbf*4.44822162
    return newtons*cal_length
    
def create_dataframe(direction):
    df = pd.DataFrame()
    if direction == "ascending":
        df["nominal_torque"] = np.linspace(min_torque, max_torque, steps_ascending)
    elif direction == "descending":
        df["nominal_torque"] = np.linspace(max_torque, min_torque, steps_descending)
    df["initial_torque"] = np.zeros(len(df.nominal_torque))
    df["final_torque"] = np.zeros(len(df.nominal_torque))
    df["mean_volts_per_volt"] = np.zeros(len(df.nominal_torque))
    df["std_volts_per_volt"] = np.zeros(len(df.nominal_torque))
    return df

def collect_data(duration):
    """Collects data from the specified channel for the duration."""
    print("\nCollecting data for {} seconds".format(duration))
    c = daqmx.channels.AnalogInputBridgeChannel()
    c.physical_channel = "{}/{}".format(device, phys_chan)
    c.name = "volts_per_volt"
    c.voltage_exc_value = 10.0
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
    
def regress(applied_torque, volts_per_volt):
    """Linearly regress applied torque versus V/V"""
    results = scipy.stats.linregress(volts_per_volt, applied_torque)
    slope, intercept, r_value, p_value, std_err = results
    return {"slope" : slope,
            "intercept" : intercept,
            "r_value" : r_value,
            "p_value" : p_value,
            "std_err" : std_err,
            "units" : "Nm/(V/V)"}
    
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
    print("Running torque arm calibration", direction)
    df = create_dataframe(direction)
    for index, torque in enumerate(df.nominal_torque):
        print("\nSet the applied force to {:.1f} lbf".format(nm_to_lbf(torque)))
        initial_force = float(input("What is the current applied force? "))
        df.initial_torque[index] = lbf_to_nm(initial_force)
        rawdata = collect_data(test_dur)
        save_raw_data(rawdata, index, direction)
        df.mean_volts_per_volt[index] = np.mean(rawdata["volts_per_volt"])
        df.std_volts_per_volt[index] = np.std(rawdata["volts_per_volt"])
        print("Mean measured voltage: {} V/V".format(df.mean_volts_per_volt[index]))
        final_force = float(input("What is the current applied force? "))
        df.final_torque[index] = lbf_to_nm(final_force)
    df["mean_torque"] = (df.initial_torque + df.final_torque)/2
    print("\n{} calibration complete".format(direction.title()))
    print("\nResults:\n")
    print(df)
    csv_folder = os.path.join("data", "processed")
    if not os.path.isdir(csv_folder):
        os.makedirs(csv_folder)
    csv_path = os.path.join(csv_folder, direction + ".csv")
    df.to_csv(csv_path, index=False)
    regression = regress(df.mean_torque, df.mean_volts_per_volt)
    print("\n{} regression:".format(direction.title()))
    for k, v in regression.items():
        print(k, ":", v)
    return df, regression

def main():
    print("Calibrating torque arm")
    metadata = {}
    metadata["9237 physical channel"] = phys_chan
    df_asc, reg_asc = run_cal("ascending")
    df_desc, reg_desc = run_cal("descending")
    metadata["linear regression ascending"] = reg_asc
    metadata["linear regression descending"] = reg_desc
    df_all = df_asc.append(df_desc)
    reg_all = regress(df_all.mean_torque, df_all.mean_volts_per_volt)
    metadata["linear regression all"] = reg_all
    metadata["timestamp"] = time.asctime()
    save_metadata(metadata)
    if plot:
        plt.style.use("ggplot")
        plt.figure()
        plt.plot(df_asc.mean_volts_per_volt, df_asc.mean_torque, "ok", 
                 label="Meas. asc.")
        plt.plot(df_desc.mean_volts_per_volt, df_desc.mean_torque, "sb", 
                 label="Meas. desc.")
        plt.xlabel("V/V")
        plt.ylabel("Applied torque (Nm)")
        plt.plot(df_all.mean_volts_per_volt, df_all.mean_volts_per_volt*reg_all["slope"] \
                 + reg_all["intercept"], label="Lin. reg. all")
        plt.legend(loc=2)
        plt.grid(True)
        plt.show()

if __name__ == "__main__":
    main()