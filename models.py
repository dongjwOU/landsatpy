import os
import numpy as np
from osgeo import gdal
from netCDF4 import Dataset
import imp
import utils

imp.reload(utils)

from utils import parse_mtl


class DirectoryModel():

    def __init__(self, data_directory, path, row, time):
        self.dir_exists = False
        self.data_directory = data_directory
        self.path = path
        self.row = row
        self.time = time
        self.lc ='LC8'
        self.misc ='LGN00'
        self.parent_dir = ''
        self.dir_name = ''
        
    def parent_dir_to_string(self):
        # self.parent_dir = self.lc + self.path + self.row + self.time + self.misc
        self.parent_dir = self.lc + self.path + self.row + self.time + self.misc
        
    def fixpath(self):
        abspath = os.path.abspath(os.path.join(os.path.expanduser("~"), self.data_directory))
        return abspath
        
    def get_data_directory(self):
        abspath = self.fixpath()
        self.parent_dir_to_string()
        self.dir_name = os.path.join(abspath, self.lc, self.path, self.row, self.parent_dir)

    def dir_test(self):
        self.dir_exists = os.path.isdir(self.dir_name)

    def setup_dir(self):
        self.parent_dir_to_string()
        self.get_data_directory()
        self.dir_test()
        
        
class FileModel(DirectoryModel):
    
    def __init__(self, data_directory, path, row, time, file_type, band_no=None):
        DirectoryModel.__init__(self, data_directory, path, row, time)
        self.file_type = file_type
        self.band_no = band_no
        self.file_end = ''
        self.file_exists = False
        self.file_name = ''
        self.full_path = ''

        
    def set_file_end(self):
        print(self.file_type)
        if self.file_type == 'nc':
            self.file_end = '_L2.nc'
        elif self.file_type == 'tiff':
            self.file_end = '_B' + str(self.band_no) + '.TIF'
        elif self.file_type == 'txt':
            self.file_end = '_MTL.txt'
        else:
            print("You havn't given a valid file type")
            
    def file_name_to_string(self):
        self.file_name = self.lc + self.path + self.row + self.time + self.misc + self.file_end
        
    def set_full_path(self):
        self.full_path = os.path.join(self.dir_name, self.file_name)
        # print('File name is: ', self.file_name)
        # print('Full path is: ', self.full_path)

    def file_test(self):
        self.file_exists = os.path.isfile(self.full_path)

    def setup_file(self):
        self.setup_dir()
        self.set_file_end()
        self.file_name_to_string()
        self.set_full_path()
        self.file_test()
        
class GeotiffBandModel(FileModel):
    
    def __init__(self, data_directory, path, row, time, file_type='tiff', band_no=None):
        FileModel.__init__(self, data_directory, path, row, time, file_type, band_no = band_no)
        
    def open_tiff(self, tiff_file):
        if self.file_exists:
            return gdal.Open(tiff_file)
        else:
            print("Error!")
            
    def data(self, bounds):
        self.setup_file()
        print(self.full_path)
        gdo = self.open_tiff(self.full_path)
        tiff_array = gdo.ReadAsArray(bounds[0], bounds[1], bounds[2], bounds[3])
        # tiff_array = gdo.ReadAsArray()

        tiff_array = np.array(tiff_array, dtype=np.int16)
        [cols,rows] = tiff_array.shape
        trans       = gdo.GetGeoTransform()
        proj        = gdo.GetProjection()
        nodatav     = None # gdo.GetNoDataValue()
        print("Transform: %s\n Projection: %s\n No Data Value: ´%s" % (trans, proj, nodatav))
        gdo = None
        return tiff_array

class GeotiffMetadata(FileModel):
    
    def __init__(self, data_directory, path, row, time, file_type='txt', band_no=None):
        FileModel.__init__(self, data_directory, path, row, time, file_type, band_no = band_no)
        self.mtl_dict = {}
        
    def data(self):
        self.setup_file()
        self.mtl_dict = parse_mtl(self.full_path)
        return self.mtl_dict
        
class NetcdfModel(FileModel):
    
    def __init__(self, data_directory, path, row, time, file_type='nc', band_no=None, cropping=False):
        FileModel.__init__(self, data_directory, path, row, time, file_type, band_no = band_no)
        self.hit = 0
        self.variables_list = []
        self.cropping = cropping
    
    def connect_to_nc(self, dims = False):
        # print("Connecting to NetCDF file")
        self.hit += 1
        # print("You have hit the NetCDF file %d times" % self.hit)
        self.nc = Dataset(self.full_path, 'r')
        if dims:
            self.dimensions = self.nc.dimensions
            self.theta_v = self.nc.THV
            self.theta_0 = self.nc.TH0
            self.phi_v = self.nc.PHIV
            self.phi_0 = self.nc.PHI0
        return self.nc
    
    def set_variables_list(self, netcdf_file):
        variables_list = []
        for item in netcdf_file.variables.keys():
            variables_list.append(item)
        self.variables_list = variables_list
    
    def get_variables_list(self):
        self.setup_file()
        netcdf_file = self.connect_to_nc()
        self.set_variables_list(netcdf_file)
        _list = self.variables_list
        netcdf_file.close
        return _list
    
    def data(self, var_name):
        '''
        Get data from netcdf file to save on disk.
        Can get subset of data by supplying upper left pixel and one side of square length.
        '''
        self.setup_file()
        self.connect_to_nc()
        nc = self.nc
        if self.cropping == True:
            result = np.array(nc.variables[var_name])
        else:
            result = np.array(nc.variables[var_name])
        # result = np.array(nc.variables[var_name])[-1024:,-1024:]
        # result = np.array(nc.variables[var_name])[:1024,:1024]
        nc.close()
        # self.nc.close()
        return result

    def pixel_data(self, var_name, pxl):
        self.setup_file()
        self.connect_to_nc()
        nc = self.nc
        result = np.array(nc.variables[var_name][pxl[0], pxl[1]])
        nc.close()
        # self.nc.close()
        return result

    def rectangle_data(self, var_name, pxl_ul, pxl_br):
        self.setup_file()
        self.connect_to_nc()
        nc = self.nc
        result = np.array(nc.variables[var_name][pxl_ul[0]:pxl_br[0], pxl_ul[1]:pxl_br[1]])
        nc.close()
        # self.nc.close()
        return result


class NetcdfVarModel(FileModel):
    
    def __init__(self, data_directory, path, row, time, var_name, file_type='nc', band_no=None, cropping=False):
        FileModel.__init__(self, data_directory, path, row, time, file_type, band_no = band_no)
        self.hit = 0
        self.var_name = var_name
        self.variables_list = []
        self.cropping = cropping

    def setup_var(self):
        self.full_path_var = os.path.join(self.dir_name, self.lc + self.path + self.row + self.time + self.misc+'_'+self.var_name+ '.nc')

    def connect_to_nc(self, dims=False):
        # print("Connecting to NetCDF file")
        self.hit += 1
        # print("You have hit the NetCDF file %d times" % self.hit)
        self.file_name = self.lc + self.path + self.row + self.time + self.misc + '_' + self.var_name + '.nc'
        self.full_path = os.path.join(self.dir_name, self.file_name)
        print(self.full_path)
        self.nc = Dataset(self.full_path, 'r')
        if dims:
            self.dimensions = self.nc.dimensions
            self.theta_v = self.nc.THV
            self.theta_0 = self.nc.TH0
            self.phi_v = self.nc.PHIV
            self.phi_0 = self.nc.PHI0
        return self.nc
    
    def set_variables_list(self, netcdf_file):
        variables_list = []
        for item in netcdf_file.variables.keys():
            variables_list.append(item)
        self.variables_list = variables_list
    
    def get_variables_list(self):
        self.setup_file()
        netcdf_file = self.connect_to_nc()
        self.set_variables_list(netcdf_file)
        _list = self.variables_list
        netcdf_file.close
        return _list
    
    def data(self, var_name, ul=(1000,1000), len_sq=2000):
        self.setup_file()
        self.connect_to_nc()
        nc = self.nc
        if self.cropping == True:
            result = np.array(nc.variables[var_name])[ul[0]:len_sq,ul[1]:len_sq]
        else:
            result = np.array(nc.variables[var_name])[ul[0]:ul[0]+len_sq,ul[1]:ul[1]+len_sq]
        # result = np.array(nc.variables[var_name])[-1024:,-1024:]
        # result = np.array(nc.variables[var_name])[:1024,:1024]
        nc.close()
        # self.nc.close()
        return result

    def pixel_data(self, var_name, pxl):
        self.setup_file()
        self.connect_to_nc()
        nc = self.nc
        result = np.array(nc.variables[var_name][pxl[0], pxl[1]])
        nc.close()
        # self.nc.close()
        return result

    def rectangle_data(self, var_name, pxl_ul, pxl_br):
        self.setup_file()
        self.connect_to_nc()
        nc = self.nc
        result = np.array(nc.variables[var_name][pxl_ul[0]:pxl_br[0], pxl_ul[1]:pxl_br[1]])
        nc.close()
        # self.nc.close()
        return result       

