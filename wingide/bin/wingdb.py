#!/usr/bin/env python
#########################################################################
""" wingdb.py    -- Top-level command used internally by Wing to
                    start a debug process.
                    
Copyright (c) 2000-2014, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

"""
#########################################################################

# Only import a few modules at the top-level 
import os.path
import sys

# Start without translation -- this gets changed once netserver is found
_ = lambda x: x

# For trouble-shooting, set environment variable or uncomment line below
def _GetDefaultPrintAllTracebacks():
  return os.environ.get('WINGDB_PRINT_ALL_TRACEBACKS', 0)
kPrintAllTracebacks = _GetDefaultPrintAllTracebacks()
if kPrintAllTracebacks:
  os.environ['WINGDB_PRINT_ALL_TRACEBACKS'] = '1'
  
# Utils for dealing w/ Python 2.x vs. 3.x
if sys.hexversion >= 0x03000000:
  def has_key(o, key):
    return key in o
else:
  def has_key(o, key):
    return o.has_key(key)
  
# Set __file__ if not already set; this is an internal value so is kosher
try:
  __file__
except NameError:
  __file__ = sys.argv[0]

# Maintain a reference to the minimalwin32 module once it is loaded; it is
# removed from sys.modules
_minimal_win32_module = None
def _GetUnicodeEnvValue(name, default=None):
  """ Get the environment value as a unicode instance.  Needed 
  because getting the unicode value on win32 involves an win32 api call """
  
  if sys.version_info >= (3, 0):
    return os.environ.get(name, default)
  
  if sys.platform == 'win32':
    global _minimal_win32_module
    if _minimal_win32_module is None:
      _minimal_win32_module = _LoadModuleFromWingbaseDir('minimalwin32')
      sys.modules.pop('minimalwin32', None)
      
    value = _minimal_win32_module.GetEnvironmentVariable(name, default)
    return value
  
  value = os.environ.get(name)
  if value is None:
    return default
  
  encoding = sys.getfilesystemencoding()
  if encoding is None:
    encoding = sys.getdefaultencoding()
    
  return unicode(value, encoding, 'replace')

def _GetWingDirs(argv):
  """ Gets winghome & usersettings dir if __name__ is __main__.  Returns
  (None, None) if unable to retrieve the dirs for some reason. """

  if __name__ != '__main__':
    return None, None

  import os

  winghome = _GetUnicodeEnvValue('WINGDB_WINGHOME')
  if winghome is not None:
    try:
      del os.environ['WINGDB_WINGHOME']
      user_settings = _GetUnicodeEnvValue('WINGDB_USERSETTINGS')
      if user_settings is not None:
        del os.environ['WINGDB_USERSETTINGS']
      return winghome, user_settings
    except:
      if kPrintAllTracebacks:
        import traceback
        traceback.print_exc(file=sys.__stderr__)
    
  try:
    winghome = os.path.dirname(os.path.dirname(os.path.abspath(argv[0])))
    return winghome, None
  except:
    if kPrintAllTracebacks:
      sys.__stderr__.write('WINGDB ARGS:' + str(argv))
      sys.__stderr__.write('\n')
      import traceback
      traceback.print_exc(file=sys.__stderr__)
  
  return None, None

#########################################################################
# Temporary, in-memory logger; used until we know where to send the messages
#########################################################################
class CTempLog:
  """ Temporarily log messages to a list. """

  def __init__(self):
    self.fEntries = []
    
  def out(self, *args):
    """ Save msg in fEntries """

    args = map(str, args)
    first = 1
    for s in args:
      if first:
        first = 0
      else:
        self.write(' ')
      self.write(s)
    
  def write(self, msg):
    """ Save msg in fEntries """
    
    if msg[-1:] == '\n':
      msg = msg[:-1]
    self.fEntries.append(msg)
    
  def write_entries(self, log):
    """ Write fEntries to out object via it's out method. """
    
    for entry in self.fEntries:
      log.out(entry)

  def clear(self):
    """ Clear all entries. """
    
    self.fEntries = []
  
#########################################################################
# Argument parsing
#########################################################################

def _ParseSingleArg(err, arg_index, func = None, choices = None):
  """ Parse a single arg from argv; print usage if arg is incorrect.  Applies
  func to the value if func is not None and look up value in choices map
  if choices is not None. """

  try:
    value = sys.argv[arg_index]

    # Transform value if function is provided 
    if func != None:
      value = func(value)
    
    # Look up value in choices if choices is not None
    if choices != None:
      value = choices[value]

    return value

  except:
    if kPrintAllTracebacks:
      import traceback
      traceback.print_exc(file=sys.__stderr__)
    sys.exit(2)
    
def _LogfileTransform(value):
  """ Transformation function for logfile arg. """
  
  value = eval(value)
  
  if value == '<none>':
    return None
  else:
    return value
  
def _HostportTransform(hostport):
  """ Transformation function for host:port arg. """
  
  colonpos = hostport.index(':')
  host = hostport[0:colonpos]
  if host == '':
    host = '127.0.0.1'
  port = int(hostport[colonpos+1:])
  return host, port
 
def _ParseEnvArgs(err):
  """Parses parameters to the debug process from the WINGDB_* environment
  variables.  Returns a dictionary of values, or an empty dict if all
  the required args were not found.
  
  All environment values should be passed in as utf-8 encoded strings.

  The supported envs are:
  
  WINGDB_HOSTPORT -- The host and port to connect to, in host:port form
                     (default=localhost:50005)
  WINGDB_FILENAME -- The file to debug, if not given on the command line
  WINGDB_STEPINTO -- 0 or 1 to indicate whether to stop on the first line of
    code (defaults=don't stop)
  WINGDB_LOGFILE -- The full path to a diagnostic log file (default=no logging)
  WINGDB_LOGVERYVERBOSE -- Whether to print extremely verbose low-level
    logging (default=off)
  WINGDB_WAIT_ON_EXIT -- Whether the debug process should wait on exit
    for further interaction with the debugger (default=don't wait)
  WINGDB_ENV_FILE -- When given, the debugger will load environment from
    this file and then exec sys.executable in the environment.  The environment
    file contains a sequence of byte strings, each separated by a '\0' byte.
    The 1st of every pair is a key and the 2nd is the value. (default=run in
    inherited environment)
  WINGDB_WINGHOME -- The Wing installation directory (default=compute
    based on location of this file)
  WINGDB_USERSETTINGS -- The Wing User Settings directory, used only
    to find the debugger implementation if provided by a patch (default=None)

  These optional envs are used only when launching from Wing:
  
  WINGDB_ATTACHPORT -- The port number to listen on for attach connections
    if connecting back to the IDE on WINGDB_HOSTPORT fails or if the IDE
    detaches (default=don't listen)
  WINGDB_SPAWNCOOKIE -- An identifier used later to determine if the debug
    process was launched by the IDE (default=None)
  
  These optional envs are only used to support Python < 2.6; in Python 2.6+
  set PYTHONIOENCODING instead:
  
  WINGDB_STDOUT_ENCODING -- Sets the encoding to use for stdout
  WINGDB_STDIN_ENCODING -- Sets the encoding to use for stdin

  These envs may be set internally and should not be altered:
  
  WINGDB_PARENT_PIDS -- Parent process IDs, used to determine which processes
    are child processes even if there is an intervening non-Python process
    
  """
  
  import os

  found_envs = set()
  first_addtl_arg = 1
  
  def get_env(env, default=None, transform=None):
    
    if env in os.environ:
      found_envs.add(env)
      
    try:
      
      try:
        # Python 3.2+
        bytes_val = os.environb.get(env, default)
        if bytes_val is not None:
          unicode_val = str(bytes_val, 'utf-8')
        else:
          unicode_val = None
      except:
        # Python 2.x
        if sys.hexversion < 0x03000000:
          str_val = os.environ.get(env, default)
          if str_val is not None:
            unicode_val = unicode(str_val, 'utf-8')
          else:
            unicode_val = None
        # Python 3.0 and 3.1
        # XXX This case may fail due to encoding mismatch
        else:
          unicode_val = os.environ.get(env, default)

      # Avoid using 'callable' because it does not exist
      # in Python 3.0 and 3.1
      try:
        unicode_val = transform(unicode_val)
      except:
        pass
        
    except:
      if kPrintAllTracebacks:
        import traceback
        traceback.print_exc(file=sys.__stderr__)
      return default
      
    return unicode_val

  args = {}

  args['host'], args['port'] = get_env('WINGDB_HOSTPORT', 'localhost:50005', _HostportTransform)
  if not args['host'] or args['port'] <= 0:
    return {}

  filename = get_env('WINGDB_FILENAME', None)
  if filename is None:
    if len(sys.argv) > 1:
      filename = sys.argv[1]
      if not os.path.exists(filename):
        return {}
      first_addtl_arg += 1
    else:
      return {}
  args['filename'] = filename
  
  args['attachport'] = get_env('WINGDB_ATTACHPORT', -1, int)
  args['firststop'] = get_env('WINGDB_STEPINTO', 0, int)
  args['logfile'] = get_env('WINGDB_LOGFILE', None)
  args['veryverboselog'] = get_env('WINGDB_LOGVERYVERBOSE', 0, int)
  args['waitonexit'] = get_env('WINGDB_WAIT_ON_EXIT', 0, int)
  args['execinenv'] = get_env('WINGDB_ENV_FILE', None)
  # Only used in Python < 2.6; set PYTHONIOENCODING instead in other cases
  args['stdoutencoding'] = get_env('WINGDB_STDOUT_ENCODING', None)
  args['stdinencoding'] = get_env('WINGDB_STDIN_ENCODING', None)
  
  # Check if debug file exists and is a file
  if not os.path.exists(filename):
    err.write(_('wingdb.py: Error: Debug file does not exist:'))
    err.write(filename)
    sys.exit(1)
  if not os.path.isfile(filename):
    err.write(_('wingdb.py: Error: Debug file is not a file:'))
    err.write(filename)
    sys.exit(1)
    
  # Remove the envs
  for env in found_envs:
    del os.environ[env]
    
  # Adjust sys.argv
  del sys.argv[:first_addtl_arg]

  return args 
  
def _ParseArgv(err):
  """ Parses sys.argv, which contains parameters encoded by position, and 
  returns dictionary of values.
  
  As of Wing 5.1, the preferred way to pass data to the debug process is
  in environment variables.  See _ParseEnvArgs above.
  
  The parameters allowed are defined as follows by position in sys.argv:

    0) This script's name
    
    1) host:port indicates where Wing is listening for reverse connection 
    from this debug process.

    2) attachport, where the debug process will listen for attach requests
    when not connected to a debug process.

    3) One of --first-stop to stop on the first line of the debug program, 
    or --no-first-stop to run to first breakpoint or completion.

    4) logfile for debug server internals.  One of <none> for no logging,
    <stderr>, <stdout>, or a file name in which to log extra error output.
    The parameter should be encoded as a Python expression that can
    be parsed by eval().  This avoids problems with special chars
    in file names.  For example, "r'mylog'" is a valid value.

    5) optional --very-verbose-log to turn on core logging support if it
    is present
    
    6) One of --wait-on-exit or --nowait-on-exit.  When set to wait-on-exit, 
    the debugger will wait for user to hit a key before exiting entirely.

    7) Optional --stdout-encoding=<encoding>.  Sets sys.stdout.encoding &
    sys.stderr.encoding to given <encoding> string iff encoding is valid
    
    8) Optional --stdin-encoding=<encoding>.  Sets sys.stdin.encoding
    to given <encoding> string iff encoding is valid
    
    9) Optional --exec-in-env=<pathname>.  Will load environment from
    file and then exec sys.executable w/ all arguments except this one
    in the environment.  The environment file contains a sequence of byte
    strings, each separated by a '\0' byte.  The 1st of every pair is a
    key and the 2nd is the value.
    
    10) filename, which is a Python expression that can be passed to eval()
    that evaluates to the name of the file to debug.

  The dictionary returned from this function contains:
    
    host: host to connect back to
    port: port to connect back to
    attachport: port # to listen far attach requests on
    firststop: whether to stop on first line
    logfile: <none>, <stderr>, <stdout>, or a file name
    veryverboselog: whether very verbose is on
    waitonexit: whether to wait for a keystroke when the program exits
    stdoutencoding: output encoding if specified or None
    stdinencoding: input encoding if specified or None
    filename: name of the python file to debug
    execinenv: name of file with env to set if specified or None

  """

  import os

  args = {}

  # Parse args and store value in dictionary to return
  args['host'], args['port'] = _ParseSingleArg(err, 1, _HostportTransform)
  args['attachport'] = _ParseSingleArg(err, 2, int)
  args['firststop'] = _ParseSingleArg(err, 3, choices = {"--no-first-stop": 0,
                                                         "--first-stop": 1})
  args['logfile'] = _ParseSingleArg(err, 4, _LogfileTransform)
  args['veryverboselog'] = (sys.argv[5] == '--very-verbose-log')
  next = 5
  if args['veryverboselog']:
    next = next + 1
  args['waitonexit'] = _ParseSingleArg(err, next, choices = {"--nowait-on-exit": 0,
                                                             "--wait-on-exit": 1})
  next = next + 1

  # These are only used for Python < 2.6; we set env PYTHONIOENCODING
  # as well, which is used in Python 2.6+
  if sys.argv[next].find('--stdout-encoding=') == 0:
    args['stdoutencoding'] = sys.argv[next][len('--stdout-encoding='):]
    next = next + 1
  else:
    args['stdoutencoding'] = None

  if sys.argv[next].find('--stdin-encoding=') == 0:
    args['stdinencoding'] = sys.argv[next][len('--stdin-encoding='):]
    next = next + 1
  else:
    args['stdinencoding'] = None
    
  if sys.argv[next].startswith('--exec-in-env='):
    args['execinenv'] = sys.argv[next][len('--exec-in-env='):]
    next = next + 1
  else:
    args['execinenv'] = None
    
  args['filename'] = filename = _ParseSingleArg(err, next, eval)
  first_addtl_arg = next + 1

  if sys.hexversion < 0x03000000:
    args['filename'] = filename = _ParseSingleArg(err, next, eval)
    first_addtl_arg = next + 1

  # Under Python 3 need to convert file name format used for working
  # around limitations on command line args
  else:
    filename_arg = _ParseSingleArg(err, next)
    
    def py2cvt(fn):
        retval = ''
        inquote = False
        i = 0
        while i < len(fn):
            if fn[i] == "'":
                inquote = not inquote
                retval += fn[i]
                i += 1
            # Rewrite r'' strings to b''
            elif fn[i] == 'r' and not inquote:
                retval += 'b'
                i += 1
            # Rewrite chr(x) with byte identifier
            elif not inquote and fn[i:].startswith('chr('):
                num = int(fn[i+len('chr('):i+fn[i:].find(')')])
                num_hex = "b'\\x%x'" % num
                retval += num_hex
                i += fn[i:].find(')') + 1
            else:
                retval += fn[i]
                i += 1
        return retval
    
    # Assumes reported file system encoding in IDE and debug process match
    try:
      kFileSystemEncoding = sys.getfilesystemencoding()
    except:
      kFileSystemEncoding = None
    try:
      if kFileSystemEncoding is None:
        kFileSystemEncoding = sys.getdefaultencoding()
    except:
      kFileSystemEncoding = 'latin_1'
      
    # Set to mbcs on win32 and python 3.6
    if sys.platform == 'win32' and sys.version_info >= (3, 6):
      kFileSystemEncoding = 'mbcs'
    
    cvt = py2cvt(filename_arg)
    byte_str = eval(cvt)
    
    args['filename'] = filename = byte_str.decode(kFileSystemEncoding)
    first_addtl_arg = next + 1
    
  # Check if debug file exists and is a file
  if not os.path.exists(filename):
    err.write(_('wingdb.py: Error: Debug file does not exist:'))
    err.write(filename)
    sys.exit(1)
  if not os.path.isfile(filename):
    err.write(_('wingdb.py: Error: Debug file is not a file:'))
    err.write(filename)
    sys.exit(1)
    
  # Prune args down to just args for the debugged program
  del sys.argv[:first_addtl_arg]
  return args


#########################################################################
# Debug server access
#########################################################################
def GetVersionTriple():
  """ Return 3 element tuple (major, minor, micro) for the version of
  the python interpreter we're running in. """
  
  if sys.hexversion >= 0x02030000 and sys.hexversion < 0x02040000:
    ff000000_mask = eval('int("4278190080")')
  else:
    ff000000_mask = eval('0xff000000')
  return ((sys.hexversion & ff000000_mask) >> 24,
          (sys.hexversion & 0x00ff0000) >> 16,
          (sys.hexversion & 0x0000ff00) >> 8)

def _LoadModuleFromDir(mod_name, dir_name):
  """ Load a module from a specific directory.  Will raise ImportError or any 
  other exception that import does if module can't be loaded """

  import imp

  fp, pathname, description = imp.find_module(mod_name, [dir_name])
  try:
    return imp.load_module(mod_name, fp, pathname, description)
  finally:
    fp.close()  

def _GetPatchDirList(winghome, user_settings):
  """ Return list of all patch dirs, ordered from lowest to highest """
  
  _patchsupport = None
  
  subdir_list = ['bin', 'src']
  for subdir in subdir_list:
    try:
      _patchsupport = _LoadModuleFromDir('_patchsupport', winghome + '/' + subdir)
    except ImportError:
      _patchsupport = None
    if _patchsupport is not None:
      break
    
  if _patchsupport is None:
    return []
  
  patch_dir_list = _patchsupport.FindAllPatchDirs(winghome, user_settings)
  patch_dir_list.reverse()
  return patch_dir_list

def _CreateMetaImporter(winghome, user_settings=None, logger=None):
  """ Create meta importer to support .wingcode files and patches.  Note
  that this function relies on the calling code to clean up the changes
  to sys """
  
  dbg_subdir = 'bin/dbg'
  
  mergeimporter = _LoadModuleFromWingbaseDir('mergeimporter', winghome)
  
  meta = mergeimporter.MergeDirImporter(logger=logger)
  if logger is not None:
    logger.write('Created meta importer')
  
  def _TryCreateDir(dirname):
    if os.path.exists(dirname):
      return
  
    try:
      os.makedirs(dirname, mergeimporter.MergeDirImporter.CACHE_DIR_UMASK)
    except (IOError, OSError):
      if logger is not None:
        logger.write('Could not create directory: ' + repr(dirname) + '\n')
    else:
      if logger is not None:
        logger.write('Created directory: ' + repr(dirname) + '\n')
    
  cache_dir = None  
  if user_settings is not None:
    cache_dir = user_settings + '/debugger-pyc'
    _TryCreateDir(cache_dir)

  patch_dir_list = _GetPatchDirList(winghome, user_settings)
  
  for name in ['debug', 'wingbase']:
    src_name = winghome + '/src/' + name
    pkg_in_dbg_dir = winghome + '/' + dbg_subdir + '/src/' + name
      
    if cache_dir is not None:
      sub_cache_dir = cache_dir + '/' + name
      _TryCreateDir(sub_cache_dir)
      meta.add_cache_dir(src_name, sub_cache_dir)

    meta.add_dir(pkg_in_dbg_dir, name)
    meta.add_dir(src_name, name)
    
    for patch_dir in patch_dir_list:
      pkg_in_patch = patch_dir + '/bin/dbg/src/' + name

      if os.path.isdir(pkg_in_patch):
        meta.add_dir(pkg_in_patch, name)

  return meta

def _LoadModuleFromWingbaseDir(mod_name, winghome=None):
  
  import os
  
  dbg_subdir = 'bin/dbg'
  mod_base_name = mod_name + '.py'
    
  # wingdb.py is either in WINGHOME/bin or WINGHOME/src
  dirname = os.path.dirname(__file__)
  if winghome is None:
    winghome = os.path.dirname(dirname)
    
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
  
  mergeimporter = _LoadModuleFromDir(mod_name, os.path.dirname(mod_full_path))
  
  return mergeimporter
  
def FindNetServerModule(winghome, user_settings=None, logger=None):
  """ Finds wing's netserver module given winghome path name.  Does not write
  to log so it can be called from wingdbstub. """
  
  import time

  # Work around win32 path joining problems
  if sys.platform == 'win32' and winghome[-1] == '\\':
    winghome = winghome[:-1]

  # Names of modules & packages to keep -- copy reg is used by pickle
  to_keep = ['encodings', 'codecs', 'atexit', 'gettext', 'stackless', 'linecache']
  if sys.version_info < (3, 0):
    to_keep.append('copy_reg')
    to_keep.append('thread')
  else:
    to_keep.append('copyreg')
    to_keep.append('_thread')
  if sys.platform == 'win32':
    to_keep.append('msvcrt')

  prev_mods = list(sys.modules.keys())
  orig_path = list(sys.path)
  saved_meta_path = list(sys.meta_path)
  
  meta = _CreateMetaImporter(winghome, user_settings, logger)
  start = time.time()
  sys.meta_path.insert(0, meta)
  
  try:
    findmodules = None
    try:
      from debug.tserver import findmodules
      from debug.tserver import netserver
    except ImportError:
      import traceback
      
      etype, value, tb = sys.exc_info()
      dir_list_repr = repr(meta.dir_list)

      if kPrintAllTracebacks:
        sys.__stderr__.write('Trying to import netserver from %s\n' % (dir_list_repr, ))
        traceback.print_exc(file = sys.__stderr__)

      if logger is not None:
        logger.write('Trying to import netserver from %s\n' % (dir_list_repr, ))
        # Lines for the logger might be in the module or attached
        # to the exception.  Use standard traceback if nothing else is
        # available
        if findmodules is None:
          logger.write('Unable to import findmodules')
          try:
            logged_lines = value.logged_lines
          except AttributeError:
            logged_lines = traceback.format_exception(etype, value, tb)
        else:
          logger.write('Successfully imported findmodules')
          logged_lines = list(findmodules.gLoggedLines)
          del findmodules.gLoggedLines[:]
          logged_lines.extend(traceback.format_exception(etype, value, tb))
          
        for line in logged_lines:
          logger.write(line)

      # Reraise any exception, note that bare raise may re-raise the 
      # AttributeError caught above
      raise value

    if logger is not None:
      logger.write('Loading code for debugger took %s seconds'
                   % ((time.time() - start), ))
      
    global _
    _ = netserver.abstract._
    netserver.abstract._SetWingHome(winghome)
    return netserver
    
  # Restore sys.path and remove modules that were added to sys.modules
  finally:
    sys.path = orig_path
    sys.meta_path = saved_meta_path
    for key in list(sys.modules.keys()):
      first_name = key.split('.')[0]
      if not key in prev_mods and first_name not in to_keep:
        del sys.modules[key]

def CreateServer(host, port, attachport, firststop, err, netserver, 
                 pwfile_path):
  """ Creates server. Writes traceback to err and returns None if creation
  fails. """

  # Create the server
  try:  
    err.out(_("Network peer is "), host, "port", port)
    err.out(_("Attach port = "), attachport)
    err.out(_("Initial stop = "), firststop)

    # Only listen locally if attachport is an int or doesn't contain ':'
    if type(attachport) == type(1) or attachport.find(':') == -1:
      attachport = '127.0.0.1:' + str(attachport)
    internal_modules = []
    mod = sys.modules.get(__name__)
    if mod is not None and mod.__dict__ is globals():
      internal_modules.append(mod)
    return netserver.CNetworkServer(host, port, attachport, err, firststop, 
                                    pwfile_path, internal_modules=tuple(internal_modules))

  # Cook exceptions for better display
  except:
    err.out(_("wingdb.py: Could not create debug server"))
    raise
  
def DebugFile(netserver, server, filename, err, fs_encoding, sys_path=None):
  """ Debug the given file. Writes any exception to err. """
  
  import os
  
  # Run the session
  try:
    filename = os.path.abspath(filename)
    try:
      pfilename = unicode(filename, fs_encoding)
    except:
      pfilename = filename
    err.out(_("wingdb.py: Running %s") % pfilename)
    os.environ['WINGDB_ACTIVE'] = str(netserver.dbgserver.dbgtracer.getpid())
    if sys_path is not None:
      sys.path = sys_path
    exit_code = server.Run(filename, sys.argv)

  # Cook exceptions for better display
  except:
    exit_code = -1
    err.out(_("wingdb.py: Server exiting abnormally on exception"))
    raise
  
  return exit_code

def CreateErrStream(netserver, logfile, very_verbose=0):
  """ Creates error stream for debugger. """
  
  file_list = []
  if logfile != None:
    file_list.append(logfile)
  err = netserver.abstract.CErrStream(file_list, very_verbose=very_verbose)

  return err

def SetEncodingPython2(encoding, file_list, netserver):
  """ Set encoding of all file objects in file_list (Python 2.x only)"""

  # Only for Python < 2.6
  if sys.hexversion >= 0x02060000:
    raise NotImplementedError
        
  if encoding is None or netserver is None:
    return
  try:
    import codecs
    codec_info = codecs.lookup(encoding)
  except:
    return
  
  try:
    set_file_encoding = netserver.dbgserver.dbgtracer.PyFile_SetEncoding
  except AttributeError:
    return

  for single_file in file_list:
    set_file_encoding(single_file, encoding)
    
def ExecInEnv(env_file, orig_argv):
  """ Exec's wingdb again in environment loaded from given binary file using the
  provided args. """

  try:
    import os
    
    exec_argv = [sys.executable]
    for a in orig_argv:
      if not a.startswith('--exec-in-env='):
        exec_argv.append(a)   

    f = open(env_file, 'rb')
    data = f.read()
    f.close()
    
    env = {}
    if sys.version_info < (3, 0):
      parts = data.split('\0')
    else:
      parts = data.split('\0'.encode('ascii'))
    for i in range(0, len(parts), 2):
      name, value = parts[i:i+2]
      env[name] = value
        
    os.execve(exec_argv[0], exec_argv, env)
    
  except:
    sys.__stderr__.write('Failed to set environment and exec wingdb again\n')
    import traceback
    traceback.print_exc(file=sys.__stderr__)
    
def main():
  """ Parse args and then run program. """

  import os
  
  # Make sure we always give opportunity to see output when wait-on-exit is true!
  waitonexit = 0
  exit_code = None
  server = None
  err = None
  tmp_log = CTempLog()
  try:

    # Pick up exceptions
    args = {}
    try:
      
      # Delete sys.path[0] because it refers to this file's directory then save sys.path
      # for future use
      del sys.path[0]
      orig_sys_path = sys.path[:]
      
      # Get args, preferably from environment, or fall back on command line args
      orig_sys_argv = sys.argv[:]
      args = _ParseEnvArgs(tmp_log)
      if not args:
        args = _ParseArgv(tmp_log)
      
      # Re-exec if requested
      if args['execinenv']:
        ExecInEnv(args['execinenv'], orig_sys_argv)
        return

      # Find directories
      winghome, user_settings = _GetWingDirs(orig_sys_argv)
  
      waitonexit = args.get('waitonexit', waitonexit)
      
      # Find netserver
      try:
        netserver = FindNetServerModule(winghome, user_settings, tmp_log)
      except:
        import traceback
        if kPrintAllTracebacks:
          traceback.print_exc(file=sys.__stderr__)

        traceback.print_exc(file=tmp_log)
        tmp_log.out(_("wingdb.py: Error: Failed to start the debug server"))
        tmp_log.out(_("wingdb.py: Error: You may be running an unsupported version of Python"))
        tmp_log.out(_("wingdb.py: Python version = %s") % sys.version)
        tmp_log.out("wingdb.py: WINGHOME=%s" % repr(winghome))
        sys.exit(-1)
      
      # Set up encoding.  In Python 2.6+ the env PYTHONIOENCODING is used instead
      # and Python does the work for us
      if sys.hexversion < 0x02060000:
        out_encoding = args.get('stdoutencoding')
        in_encoding = args.get('stdinencoding')
        tmp_log.out("Setting stdoutencoding=%s" % str(out_encoding))
        tmp_log.out("Setting stdinencoding=%s" % str(in_encoding))
        SetEncodingPython2(out_encoding, [sys.stdout, sys.stderr], netserver)
        SetEncodingPython2(in_encoding, [sys.stdin], netserver)
      else:
        tmp_log.out("I/O encoding will be=%s" % os.environ.get('PYTHONIOENCODING', '<default>'))

      # Create error log and write tmp entries to it
      err = CreateErrStream(netserver, args['logfile'], args['veryverboselog'])
      tmp_log.write_entries(err)
      tmp_log.clear()
      
      # Create the server and run
      err.out("sys.path=%s" % repr(sys.path))
      err.out("sys.argv=%s" % repr(sys.argv))
      pwfile_path = [winghome, netserver.abstract.kPWFilePathUserProfileDir]
      server = CreateServer(args['host'], args['port'], args['attachport'], 
                            args['firststop'], err, netserver, pwfile_path)
      exit_code = DebugFile(netserver, server, args['filename'], err,
                netserver.abstract.kFileSystemEncoding, orig_sys_path)

    # Handle any exception that caused debug to fail to start up
    except:
      if kPrintAllTracebacks:
        import traceback
        traceback.print_exc(file=sys.__stderr__)

      # Find log file, if any was specified
      logfile = args.get('logfile')
      opened_file = 0
      if logfile is None or logfile == '<none>' or logfile == '<stderr>':
        file = sys.stderr
      elif logfile == '<stdout>':
        file = sys.stdout
      else:
        try:
          file = open(logfile, "a")
          opened_file = 1
        except (IOError, OSError):
          file = sys.stderr
          
      # Write log/exception info if we have a log file
      if file != None:
        
        # Write any stored up log entries
        for entry in tmp_log.fEntries:
          file.write(entry + '\n')

        # Also print traceback to log file, which can raise exceptions
        import traceback
        try:
          traceback.print_exc(file=file)
        except:
          file.write('Exception raised while printing exc')
          
        # Close file if we opened it
        if opened_file:
          file.close()

  # Always stop server and wait for user to exit if requested
  finally:
    if server != None:
      try: server.Stop()
      except: pass

    if waitonexit:
      if sys.hexversion >= 0x03000000:
        line = input(_("-- Type return or enter to exit --\n"))
      else:
        line = raw_input(_("-- Type return or enter to exit --\n"))
    
  if exit_code is not None:
    sys.exit(exit_code)

#########################################################################
# Execution starts here
#########################################################################

if __name__ == '__main__':
  main()
