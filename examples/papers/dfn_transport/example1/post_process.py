import paraview.simple as pv

import vtk
from vtk.util.numpy_support import vtk_to_numpy

import csv
import os
import shutil

import numpy as np

#------------------------------------------------------------------------------#

def read_file(file_in):
    vtk_reader = vtk.vtkXMLUnstructuredGridReader()
    vtk_reader.SetFileName(file_in)
    vtk_reader.Update()
    return vtk_reader

#------------------------------------------------------------------------------#

def read_data(vtk_reader, field):
    data = vtk_reader.GetOutput().GetCellData().GetArray(field)
    return vtk_to_numpy(data)

#------------------------------------------------------------------------------#

def plot_over_line(file_in, file_out, pts, resolution=2000):

    if file_in.lower().endswith('.pvd'):
        # create a new 'PVD Reader'
        sol = pv.PVDReader(FileName=file_in)
    elif file_in.lower().endswith('.vtu'):
        # create a new 'XML Unstructured Grid Reader'
        sol = pv.XMLUnstructuredGridReader(FileName=file_in)
    else:
        raise ValueError, "file format not yet supported"

    # create a new 'Plot Over Line'
    pol = pv.PlotOverLine(Input=sol, Source='High Resolution Line Source')

    # Properties modified on plotOverLine1.Source
    pol.Source.Point1 = pts[0]
    pol.Source.Point2 = pts[1]
    pol.Source.Resolution = resolution

    # save data
    pv.SaveData(file_out, proxy=pol, Precision=15)

#------------------------------------------------------------------------------#

def read_csv(file_in, fields=None):

    # post-process the file by selecting only few columns
    if fields is not None:
        data = list(list() for _ in fields)
        with open(file_in, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            [d.append(row[f]) for row in reader for f, d in zip(fields, data)]
    else:
        with open(file_in, 'r') as csvfile:
            reader = csv.reader(csvfile)
            data = list(reader)

    return data

#------------------------------------------------------------------------------#

def write_csv(file_out, fields, data):
    with open(file_out, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        #writer.writeheader()
        for dd in zip(*data):
            if np.isnan(np.array(dd)).any():
                print(dd)
            writer.writerow({f: d for f, d in zip(fields, dd)})

#------------------------------------------------------------------------------#

def cot_domain(file_in, step, field, num_frac, padding=6):

    cot_avg = np.zeros((step, num_frac))
    cot_min = np.zeros((step, num_frac))
    cot_max = np.zeros((step, num_frac))

    for i in np.arange(step):

        ifile = file_in+str(i).zfill(padding)+".vtu"
        vtk_reader = read_file(ifile)

        weight = read_data(vtk_reader, "cell_volumes")
        frac_num = read_data(vtk_reader, "frac_num")
        c = read_data(vtk_reader, field)

        for frac_id in np.arange(num_frac):
            is_loc = frac_num == frac_id
            weight_loc = weight[is_loc]

            cot_avg[i, frac_id] = np.sum(c[is_loc]*weight_loc)/np.sum(weight_loc)
            cot_min[i, frac_id] = np.amin(c[is_loc])
            cot_max[i, frac_id] = np.amax(c[is_loc])

    return cot_avg, cot_min, cot_max

#------------------------------------------------------------------------------#

def num_cells(file_in, num_frac, padding=6):

    i = 0

    ifile = file_in+str(i).zfill(padding)+".vtu"
    vtk_reader = read_file(ifile)

    frac_num = read_data(vtk_reader, "frac_num")
    num = np.zeros(num_frac+1, dtype=np.int)

    for frac_id in np.arange(num_frac):
        num[frac_id] = np.sum(frac_num == frac_id)

    num[-1] = np.sum(num[:-1])
    return num

#------------------------------------------------------------------------------#

def main():

    num_simul = 21

    field = "scalar"
    n_step = 300
    time_step = 0.05
    num_frac = 3

    grids = ["1k", "3k", "10k"]

    #folder_master = "/home/elle/simul/example1/"
    folder_master = "/home/elle/Dropbox/Work/PostDoc-Bergen/ANIGMA/porepy/examples/papers/dfn_transport/example1/"
    folder_master_out = "/home/elle/Dropbox/Work/PresentazioniArticoli/2019/Articles/tipetut++/Results/example1/"
    methods = ["MVEM", "Tpfa", "RT0"]

    for method in methods:
        for grid in grids:
            # store the number of cells
            num = np.zeros((num_simul, num_frac+1), dtype=np.int)
            for simul in np.arange(num_simul):

                folder_in = folder_master + "solution_" + method + "_" + grid + "_" + str(simul+1) + "/"
                folder_out = folder_master_out + method + "/"

                # in this file the constant data are saved
                file_in = folder_in + "solution_2_"

                cot_avg, cot_min, cot_max = cot_domain(file_in, n_step, field, num_frac)

                times = np.arange(n_step) * time_step
                labels = np.arange(num_frac).astype(np.str)
                labels = np.core.defchararray.add("cot_", labels)
                labels = np.insert(labels, 0, 'time')

                if not os.path.exists(folder_out):
                    os.makedirs(folder_out)

                # create the output files
                file_out = folder_out + method + "_Cmin_" + str(simul+1) + "_" + grid + ".csv"
                data = np.insert(cot_min, 0, times, axis=1).T
                write_csv(file_out, labels, data)

                # create the output files
                file_out = folder_out + method + "_Cmax_" + str(simul+1) + "_" + grid + ".csv"
                data = np.insert(cot_max, 0, times, axis=1).T
                write_csv(file_out, labels, data)

                # create the output files
                file_out = folder_out + method + "_Cmean_" + str(simul+1) + "_" + grid + ".csv"
                data = np.insert(cot_avg, 0, times, axis=1).T
                write_csv(file_out, labels, data)

                # count number of cells
                num[simul, :] = num_cells(file_in, num_frac)

                # copy outflow file
                file_in = folder_in + "outflow.csv"
                file_out = folder_out + method + "_production_" + str(simul+1) + "_" + grid + ".csv"
                shutil.copy(file_in, file_out)

            file_out = folder_out + method + "_num_cells_" + grid + ".csv"
            np.savetxt(file_out, np.atleast_2d(num), delimiter=',', fmt="%d")

if __name__ == "__main__":
    main()
