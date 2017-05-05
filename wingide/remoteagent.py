#########################################################################
""" remoteagent.py    -- Remote agent for Wing
                    
Copyright (c) 2015, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

"""
#########################################################################

import sys
import os
import traceback

WINGHOME = os.path.dirname(os.path.abspath(__file__))
#sys.path.append(WINGHOME)
#import wingdbstub

def PrependBinDbgPath():
  """ Inserts WINGHOME/bin/dbg/src at the start of sys.path iff it
  exists.  It needs to be prepended as long as this file is in WINGHOME
  and the src/wingbase directory exists """
  
  bin_dbg = os.path.join(WINGHOME, 'bin', 'dbg', 'src')
  
  if os.path.exists(bin_dbg):
    sys.path.insert(0, bin_dbg)
    
PrependBinDbgPath()

def _TryCreateDir(dirname):
  if os.path.exists(dirname):
    return

  mergeimporter = _LoadMergeImporter(WINGHOME)
  try:
    os.makedirs(dirname, mergeimporter.MergeDirImporter.CACHE_DIR_UMASK)
  except (IOError, OSError):
    print('Could not create directory: ' + repr(dirname) + '\n')
  else:
    print('Created directory: ' + repr(dirname) + '\n')
  
def _LoadMergeImporter(winghome):

  import os.path
  import imp
  
  dbg_subdir = 'bin/dbg'

  mod_name = 'mergeimporter'
  mod_base_name = 'mergeimporter.py'

  mod_full_path = None
  possible_subdir_list = [
    dbg_subdir + '/src/wingbase', 
    'src/wingbase', 
  ]
  for possible_subdir in possible_subdir_list:
    possible = os.path.join(winghome, possible_subdir, mod_base_name)
    if os.path.isfile(possible):
      mod_full_path = possible
      break
      
  if mod_full_path is None:
    raise ValueError("Could not find %s in winghome: %s" % (mod_base_name, winghome))
  
  fp, pathname, description = imp.find_module(mod_name, [os.path.dirname(mod_full_path)])
  try:
    mergeimporter = imp.load_module(mod_name, fp, pathname, description)
  finally:
    fp.close()
    
  return mergeimporter
  
def _CreateMetaImporter(winghome, user_settings=None):
  """ Create meta importer to support .wingcode files and patches"""
  
  dbg_subdir = 'bin/dbg'

  mergeimporter = _LoadMergeImporter(winghome)
  meta = mergeimporter.MergeDirImporter(logger=sys.stdout)
  print('Created meta importer')
  
  for name in ['debug', 'wingbase']:
    bin_dbg_dir = winghome + '/' + dbg_subdir + '/src/' + name
    src_name = winghome + '/src/' + name

    meta.add_dir(bin_dbg_dir, name)
    meta.add_dir(src_name, name)

  return meta

def _SetupCacheDirs(winghome, meta, user_settings):
  """Set up cache dirs in meta importer, which we can only do
  after importing miscutils to find out the user settings dir"""
  
  if user_settings is None:
    return

  cache_dir = user_settings + '/debugger-pyc'
  _TryCreateDir(cache_dir)
    
  for name in ['debug', 'wingbase']:
    src_name = winghome + '/src/' + name
    sub_cache_dir = cache_dir + '/' + name
    _TryCreateDir(sub_cache_dir)
    meta.add_cache_dir(src_name, sub_cache_dir)

  return meta

meta = _CreateMetaImporter(WINGHOME)
sys.meta_path.insert(0, meta)

from wingbase import miscutils
_SetupCacheDirs(WINGHOME, meta, miscutils.kUserWingDir)
from wingbase import wingversion
from wingbase import remote

if __name__ == '__main__':

  # Create wingdebugpw file
  miscutils.CreateInitialPasswordFile()
  
  # Set up log file
  user_dir = miscutils.kUserWingDir
  log_file = os.path.join(user_dir, 'remote-agent.log')
  log_obj = miscutils.CLoggedOutput(log_file, 1000000, truncate=False)
  sys.stderr = log_obj
  sys.stdout = log_obj
  
  print("Starting remote agent")
  print("PRODUCT=%s" % wingversion.kProduct)
  print("VERSION=%s-%s" % ('.'.join([str(v) for v in wingversion.kVersion]),
                           wingversion.kBuild))
  print("WINGHOME=%s" % miscutils._GetWingHome())
  print("WINGUSERDIR=%s" % user_dir)
  print("PYTHON=%s" % sys.executable)
  print(sys.version)
  print("ENVIRON=", os.environ)
  print("PATH=", sys.path)
  
  def failure():
    print("Usage: remoteagent.py --port=[hostname:]port [--basedir=basedir]")
    sys.exit(1)
    
  # Get host and port to connect to (host defaults to localhost)
  hostport = None
  basedir = None
  for arg in sys.argv[1:]:
    if arg.startswith('--port='):
      hostport = arg[len('--port='):]
    elif arg.startswith('--basedir='):
      basedir = arg[len('--basedir='):]
  print("hostport", hostport)
  print("basedir", basedir)
  
  if not hostport:
    failure()
    
  try:    
    if ':' in hostport:
      host, port = hostport.split(':')
      port = int(port)
      if host.strip() == '':
        host = '127.0.0.1'
    else:
      port = int(hostport)
      host = '127.0.0.1'
  except:
    failure()

  # Setup server and connect to IDE
  svr = None
  try:
    svr = remote.CRemoteServer(basedir)
    svr.Connect(host, port)
    svr.Run()
  except:
    if svr is None or not svr.fQuitting:
      print("UNEXPECTED EXCEPTION IN REMOTE AGENT")
    else:
      print("QUITTING REMOTE AGENT ON EXCEPTION")
    traceback.print_exc()
      
  