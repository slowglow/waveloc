import unittest
import os, glob
import logging

def suite():
  suite = unittest.TestSuite()
  suite.addTest(SetupTests('test_setup'))
  return suite

def setUpModule():

  from .make_SDS_data_links import make_SDS_data_links

  # get basic information
  base_path=os.getenv('WAVELOC_PATH')
  test_data_dir=os.path.join(base_path,'test_data','raw_data')
  data_dir=os.path.join(base_path,'data','TEST')
  lib_dir=os.path.join(base_path,'lib')
  if not os.path.exists(data_dir) : os.makedirs(data_dir)
  if not os.path.exists(lib_dir) : os.makedirs(lib_dir)

  # make the data links
  make_SDS_data_links(test_data_dir,'*MSEED',data_dir)

  # make link for test grid file etc
  test_files=['test_grid.search.hdr', 'coord_stations_test', 'grid.Taisne.search.hdr', 'test_channel_file']
  for tfile in test_files:
    try:
      os.symlink(os.path.join(base_path,'test_data',tfile),os.path.join(base_path,'lib',tfile))
      logging.info("Linked %s"%tfile)
    except OSError:
      logging.info("File %s already linked"%'tfile')
      logging.info("Removing old %s"%tfile)
      os.remove(os.path.join(base_path,'lib',tfile))
      os.symlink(os.path.join(base_path,'test_data',tfile),os.path.join(base_path,'lib',tfile))
      logging.info("Linked %s"%tfile)

  # make links for PDF time grids
  test_files=glob.glob(os.path.join(base_path,'test_data', 'time_grids', 'Slow*'))
  if test_files==[]: 
    logging.error('Dowload https://github.com/downloads/amaggi/waveloc/test_data.tgz and unpack it in the %s directory, then re-run'%(base_path))
  for tfile in test_files:
    try:
      os.symlink(os.path.join(base_path,'test_data','time_grids',os.path.basename(tfile)),os.path.join(base_path,'lib',os.path.basename(tfile)))
      logging.info("Linked %s"%tfile)
    except OSError:
      pass

   


class SetupTests(unittest.TestCase):

  def test_setup(self):
    self.assertTrue(True)

if __name__ == '__main__':

  from . import test_processing, test_migration, test_location, test_hdf5, test_nllstuff, test_correlation
  from . import test_double_diff, test_clustering, test_kurtogram
  import logging
  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 

  suite_list=[suite(),
    test_processing.suite(),
    test_migration.suite(),
    test_location.suite(),
    test_hdf5.suite(),
    test_nllstuff.suite(),
    test_kurtogram.suite(),
    test_correlation.suite(),
    test_clustering.suite(),
    test_double_diff.suite(),
    ]

  alltests=unittest.TestSuite(suite_list)

  unittest.TextTestRunner(verbosity=2).run(alltests)
 
