""" mergeimporter.py -- Imports modules from a series of directories for each
package similar to how merge filesystems work. This is used to implement patch
loading, so as few modules as possible should be used because any module used
cannot be patched.  Needs to be able to be loaded as a top level module and by
any python version supported by the debugger.

Copyright (c) 2004-2016, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

"""

# Compatibility note: this is used when loading the debugger so needs to
# work with all supported Python versions.  The meta path import mechanism
# was introduced in python 2.3.  Some of the details are being deprecated
# in the python 3 series but nothing is abandoned as of 3.5

import linecache
import marshal
import os
import sys
import traceback
import imp

try:
  import string
except ImportError:
  string = None

def get_importable_name(file_name):
  """ Return Python name created when given file name is imported or None
  if it can't be imported through the built in import mechanism. """

  for suffix, open_mode, stype in imp.get_suffixes():
    if file_name.endswith(suffix):
      return file_name[:-len(suffix)]
  return None

def is_identifier(s):
  """ Returns whether s is a valid Python identifer """
  
  if s == '':
    return False
  
  for i, c in enumerate(s):
    if i == 0:
      if not (c.isalpha() or c == '_'):
        return False
    else:
      if not (c.isalnum() or c == '_'):
        return False
      
  return True

def _MakeBytes(s):
  
  if sys.version_info[:2] < (3, 0):
    return str(s)
  else:
    return bytes(s, 'ascii')

def _GetTrans():
  

  if sys.version_info[:2] < (3, 0):
    f = ''.join(chr(i) for i in range(256))
    t = ''.join(chr(i) for i in reversed(range(256)))
    return string.maketrans(f, t)
  
  f = bytes(range(256))
  t = bytes(reversed(range(256)))
  # XXX 3.0 is missing .maketrans
  return bytes.maketrans(f, t)

class MergeDirImporter:
  """ Importer object to load modules and modules in packages from a list of
  directories in preference to sys.path; loads modules from internal list of
  directories even if the import is a local import within a package. This is
  so directories of patch files can be kept in separate directories, but
  loaded even when using relative imports. Designed to be used as a meta_path
  hook, which intercepts all import requests before the internal import
  mechanism attempts to resolve the import.
  
  Supports .wingcode files to obfuscate source code

  Current limitations / implementation quirks:
   * Ignores zip files in patch directory
   * List of files in patch directory is scanned when directory is added
     so files added or removed afterward are ignored
   * Path directories added last take precedence over directories added
     first
   * Source in .wingcode files must be utf8 encoded (ascii is acceptable,
     of course)
  """
  
  WING_CODE_EXT = '.wingcode'
  _TRANSLATE = _GetTrans()
  USE_OUR_METHODS_FOR_PY_FILES = False
  WRITE_EMPTY_LINECACHE_ENTRIES = True
  MAX_LOG_LEVEL = 1
  
  CACHE_DIR_UMASK = 0x1c0  # 0o700, which python 2.5 doesn't accept
  
  if sys.version_info[:2] < (3, 0):
    CODE_OBJECT_TYPE = type(is_identifier.func_code)
  else:
    CODE_OBJECT_TYPE = type(is_identifier.__code__)
  
  def __init__(self, dir_list = [], logger=None):
    self.__files_for_name = {}
    self._cache_dirs = {}
    self.dir_list = []
    
    self._logger = logger
    for dirname in dir_list:
      self.add_dir(dirname)

  def add_cache_dir(self, dirname, cache_dir):
    """ Add cache dir for a given dir.  Subdirectories of dirname
    will map to subdirectories of cache_dir.  Note that cache dirs
    are scanned when dirs are initially scanned """
    
    if os.sep != '/':
      dirname = dirname.replace(os.sep, '/')
      cache_dir = cache_dir.replace(os.sep, '/')
    
    self._cache_dirs[dirname] = cache_dir

  def add_dir(self, dirname, parent = ''):
    """ Add all files in given directory and all subdirectories.  parent 
    is the dotted name of the parent directory. """
    
    if os.sep != '/':
      dirname = dirname.replace(os.sep, '/')
    
    self.dir_list.append(dirname)
    
    if parent != '' and not parent.endswith('.'):
      parent += '.'
    
    try:
      name_list = os.listdir(dirname)
    except (IOError, OSError):
      return

    added_list = []
    for name in name_list:
      # Note os.path is safe since name is never absolute
      assert not os.path.isabs(name)
      full_path = os.path.join(dirname, name)
      if os.sep != '/':
        full_path = full_path.replace(os.sep, '/')
        
      if os.path.isdir(full_path):
        if is_identifier(name):
          self.add_dir(full_path, parent + name + '.')
          
      elif os.path.isfile(full_path):
        if full_path.endswith(self.WING_CODE_EXT):
          imp_name = name[:-len(self.WING_CODE_EXT)]
        else:
          imp_name = get_importable_name(name)
        if imp_name is not None:
          added = self._add_single_file(full_path, imp_name, parent)
          if added:
            added_list.append(full_path)

  def _log(self, msg, exc=False, level=1):
    
    if self._logger is None or level > self.MAX_LOG_LEVEL:
      return
    
    if not msg.endswith('\n'):
      msg += '\n'
    self._logger.write(msg)
      
    if exc:
      traceback.print_exc(file=self._logger)
      
  def _log2(self, msg, exc=False):
    
    self._log(msg, exc, 2)

  def _add_single_file(self, full_path, imp_name, parent):
    
    pkg_namespace = (parent != '' and imp_name == '__init__')
    if not pkg_namespace:
      full_mod_name = parent + imp_name
    else:
      full_mod_name = parent[:-1]
  
    dirname = os.path.dirname(full_path)
  
    existing = self.__files_for_name.get(full_mod_name)
    if existing is not None and existing[0] == dirname:
      file_list = existing[2]
    else:
      file_list = []
    self._add_file_to_ordered_list(full_path, file_list)
    self.__files_for_name[full_mod_name] = (dirname, pkg_namespace, file_list)

  def _add_file_to_ordered_list(self, full_path, file_list):
    """ Add / insert file in list -- the first file that can be used will be """
    
    pyc_exts = ('.pyc', '.pyo')
    if full_path.endswith(pyc_exts):
      file_list.append(full_path)
    elif full_path.endswith(self.WING_CODE_EXT):
      # .wingcode files come after .py, but before .pyc / .pyo
      i = 0
      while i < len(file_list) and not file_list[i].endswith(pyc_exts):
        i += 1
      file_list.insert(i, full_path)
    else:
      file_list.insert(0, full_path)
      
  def find_module(self, full_name, path = None):

    self._log2('find_module called, full_name = %s' % (full_name, ))
    data = self.__files_for_name.get(full_name)
    if data is not None:
      return self
    else:
      return None
    
  def load_module(self, full_name):

    data = self.__files_for_name.get(full_name)
    if data is None:
      raise ImportError('Unknown module: %s' % full_name)

    self._log2('load_module found data: %s' % (data, ))

    last_import_exc = None

    dirname, is_pkg, full_path_list = data
    for full_path in full_path_list:
      if os.sep != '/':
        full_path = full_path.replace('/', os.sep)
      if full_path.endswith(self.WING_CODE_EXT):
        mod = self._load_wing_code(full_name, full_path, is_pkg)
      elif self.USE_OUR_METHODS_FOR_PY_FILES and full_path.endswith('.py'):
        mod = self._load_wing_code(full_name, full_path, is_pkg)
      else:
        parts = full_name.split('.')
        path = os.path.dirname(full_path)
        if is_pkg:
          path = os.path.dirname(path)
        try:
          f, p, d = imp.find_module(parts[-1], [path])
          try:
            mod = imp.load_module(full_name, f, p, d)
          finally:
            if f is not None:
              f.close()
        except ImportError:
          last_import_exc = sys.exc_info()
          mod = None
        
      if mod is not None:
        self._log2('Returning module for %s using file: %r' % (full_name, full_path))
        return mod
    
    if last_import_exc is not None:
      etype, exc, tb = last_import_exc
      raise exc
    
    raise ImportError('Unknown module: %s' % full_name)

  def _load_wing_code(self, mod_name, filename, is_pkg):
    """ Load a module from a .wingcode or .py file, using a .pyc / .pyo
    file if possible """

    cache_pyc = self._get_pyc_filename_in_cache(filename)
    
    def update_linecache(co):
      """ Insert a dummy entry into linecache so it doesn't try to
      read the file; it tries over and over """
      
      if not self.WRITE_EMPTY_LINECACHE_ENTRIES:
        return
      
      linecache.cache[co.co_filename] = (None, None, [], co.co_filename)

    def try_pyc_file(src_mtime):
      """ Try loading mod from .pyc file.  Return None if not successful """
      
      if cache_pyc is None or not os.path.exists(cache_pyc):
        return None
      
      co = self._load_from_pyc(mod_name, cache_pyc, filename, mtime)
      if co is None:
        return None

      update_linecache(co)
      
      # Pretend that the .pyc file is in the same dir as the src
      basename = os.path.basename(filename)
      if cache_pyc.endswith(('.pyc', '.pyo')):
        pos = basename.rfind('.')
        if pos > 0:
          basename = basename[:pos]
        basename += cache_pyc[-4:]
        
      file_in_mod = os.path.join(os.path.dirname(filename), basename)

      mod = self._exec_mod(mod_name, file_in_mod, co, is_pkg)
      return mod
    
    try:
      f = open(filename, 'rb')
      try:
        mtime = int(os.fstat(f.fileno()).st_mtime)
        mod = try_pyc_file(mtime)
        if mod is not None:
          self._log2('Using mod loaded from .pyc: %r' % (mod_name, ))
          return mod
        
        data = f.read()
      finally:
        f.close()
    except (IOError, OSError):
      return None
    
    if data.startswith(_MakeBytes('\0')):
      data = data[1:].translate(self._TRANSLATE)

    # Cheap universal newline translating
    data = data.replace(_MakeBytes('\r\n'), _MakeBytes('\n'))
    data = data.replace(_MakeBytes('\r'), _MakeBytes('\n'))
      
    if filename.endswith(self.WING_CODE_EXT):
      compile_filename = filename[:-len(self.WING_CODE_EXT)] + '.py'      
    else:
      compile_filename = filename
    
    co = self._compile_mod(mod_name, data, filename, compile_filename)
    update_linecache(co)

    if cache_pyc is not None:
      self._write_to_pyc(cache_pyc, co, mtime)
    
    return self._exec_mod(mod_name, compile_filename, co, is_pkg)
    
  def _exec_mod(self, mod_name, filename, co, is_pkg):
    """ Exec co in a new module.  The module gets added to sys.modules before
    the co is exec'd """
    
    # Convert to byte strings in 2.x; use 'replace' so exceptions aren't thrown
    # Filenames that don't decode to fs encoding are likely to cause problems
    if sys.version_info < (3, 0):
      fs_encoding = sys.getfilesystemencoding()
      if fs_encoding is None:
        fs_encoding = sys.getdefaultencoding()
        
      if isinstance(filename, unicode):
        filename = filename.encode(fs_encoding, 'replace')
      if isinstance(mod_name, unicode):
        mod_name = mod_name.encode('ascii', 'replace')
    
    mod = imp.new_module(mod_name)
    mod.__loader__ = self
    mod.__file__ = filename

    if is_pkg:
      mod.__path__ = [os.path.dirname(filename)]
      mod.__package__ = mod_name
    else:
      name_parts = mod_name.split('.')
      if len(name_parts) > 1:
        mod.__package__ = '.'.join(name_parts[:-1])
    
    sys.modules[mod_name] = mod
    exec(co, mod.__dict__)
    return mod

  def _compile_mod(self, name, source, filename, compile_filename=None):
    """ Compile & return code object.  Assumes encoding is utf8, which is valid for
    all Wing files """
   
    if compile_filename is None:
      compile_filename = filename

    if sys.version_info[:2] >= (3, 0):
      source = str(source, 'utf8')
      
    if not source.endswith('\n'):
      source += '\n'

    co = compile(source, compile_filename, 'exec', 0, True)
    return co
  
  def _load_from_pyc(self, name, pyc_name, src_full_path=None, src_mtime=None):
    """ Try to load code object from .pyc file.  Returns None if unable to """
    
    pyc_suffix_triple = None
    for suffix_triple in imp.get_suffixes():
      if suffix_triple[0] in ('.pyc', '.pyo'):
        pyc_suffix_triple = suffix_triple
        break
    if pyc_suffix_triple is None:
      return None

    if src_mtime is None and src_full_path is not None:
      try:
        src_mtime = int(os.stat(src_full_path).st_mtime)
      except (IOError, OSError):
        src_mtime = None
        
    try:
      f = open(pyc_name, 'rb')
    except (IOError, OSError):
      return None
    
    try:
      try:
        magic = f.read(4)
        if magic != imp.get_magic():
          return None
        if src_mtime is not None:
          pyc_mtime = _MarshalRead4ByteInt(f)
          if pyc_mtime != int(src_mtime):
            return None
        else:
          f.seek(4)
          
        co = marshal.load(f)

      except:
        self._log('Unable to load code object from pyc file: %r' % (pyc_name, ), exc=True)
        return None

    finally:
      f.close()
      
    if not isinstance(co, self.CODE_OBJECT_TYPE):
      self._log('Object loaded from .pyc not a code object: %r' % (repr(co), ))
      return None
    
    self._log2('Loaded code object from .pyc file: %r' % (pyc_name, ))
    return co
      
  def _write_to_pyc(self, pyc_name, co, mtime):
    
    # Create directory if needed and the registered cache directory
    # exists
    dirname = os.path.dirname(pyc_name)
    if not os.path.exists(dirname):
      found_parent = None
      for registered_dir in self._cache_dirs.values():
        if os.path.normpath(dirname).startswith(os.path.normpath(registered_dir)):
          found_parent = registered_dir
          break
      if found_parent is None:
        self._log('Unable to find registered cache directory for: %r'
                  % (pyc_name, ))
        return False
      if not os.path.exists(found_parent):
        self._log('Registered cache directory for .pyc does not exist: %r'
                  % (pyc_name, ))
        self._log('  Registered cache directory: %r' % (found_parent, ))
        return False
        
      try:
        os.makedirs(dirname, self.CACHE_DIR_UMASK)
      except (IOError, OSError):
        self._log('Failed to create directory: %r' % (dirname, ))
        return False
      
      self._log('Create directory: %r' % (dirname, ))
    
    try:
      f = open(pyc_name, 'wb')
    except (IOError, OSError):
      self._log('Writing .pyc file failed: %r' % (pyc_name, ), exc=True)
      return
    
    try:
      try:
        f.write(imp.get_magic())
        _MarshalWrite4ByteInt(0, f)
        marshal.dump(co, f)
        
        f.seek(4)
        _MarshalWrite4ByteInt(mtime, f)
        failed = False
        self._log('Successfully wrote .pyc file: %r' % (pyc_name, ))
      except:
        self._log('Writing .pyc file failed: %r' % (pyc_name, ), exc=True)
        failed = True
        
    finally:
      f.close()
  
    if failed:
      try:
        os.remove(pyc_name)
      except (IOError, OSError):
        # May be removed by another process
        self._log('Removing .pyc file failed (may be removed by other process): %r'
                  % (pyc_name, ), exc=True)
      
    return (not failed)
  
  def _get_pyc_filename_in_cache(self, full_path):
    
    full_path = os.path.normpath(full_path)
    
    dirname = os.path.dirname(full_path)
    cache_dir = self._get_cache_dir(dirname)
    if cache_dir is None:
      return None
    
    name = os.path.basename(full_path)
    if sys.version_info[:2] < (3, 0):
      name += '.cpython-%s%s' % sys.version_info[:2]
    else:
      name += '.' + imp.get_tag()
      
    if __debug__:
      name += '.pyc'
    else:
      name += '.pyo'
      
    cache_full_path = cache_dir + '/' + name
    return cache_full_path
    
  def _get_cache_dir(self, dirname):
    """ Get cache dir for source directory.  The cache directory
    may be a sub directory of one of the registered directories """

    if os.sep != '/':
      dirname = dirname.replace(os.sep, '/')
    
    parts = dirname.split('/')
    for i in range(len(parts), -1, -1):
      cache_dir = self._cache_dirs.get('/'.join(parts[:i]))
      if cache_dir is not None:
        if i < len(parts):
          cache_dir += '/' + '/'.join(parts[i:])
        return cache_dir
      
    return None

def _MarshalWrite4ByteInt(val, f):
  
  byte_list = [
    val & 0xff,
    (val >> 8) & 0xff, 
    (val >> 16) & 0xff, 
    (val >> 24) & 0xff, 
  ]
  
  if sys.version_info[:2] < (3, 0):
    s = ''.join(map(chr, byte_list))
  else:
    s = bytes(byte_list)
    
  f.write(s)
  
def _MarshalRead4ByteInt(f):
  
  byte_str = f.read(4)
  
  if sys.version_info[:2] < (3, 0):
    val_list = map(ord, byte_str)
  else:
    val_list = byte_str

  val = (val_list[0] 
         | (val_list[1] << 8)
         | (val_list[2] << 16)
         | (val_list[3] << 24))
  return val
