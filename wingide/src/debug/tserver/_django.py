#########################################################################
""" _django.py -- Django hooks for the debugger

Copyright (c) 1999-2012, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

"""
#########################################################################

import os, sys
import traceback
from . import _extensions
from . import dbgutils

# The name of the module to watch for that indicates presence of Django
kIndicatorModuleName = 'django.template'

# Turn this on to debug this module -- prints diagnostics and disables
# munging of locals and globals in template frames
kDebug = 0

def get_code(func):
  try:
    return func.func_code
  except:
    return func.__code__
  
def get_func(obj):
  try:
    return obj.__func__
  except:
    return obj
  
########################################################################
class _SubLanguageHook(_extensions._SubLanguageHook):
  """Implementation of debugger hooks for Django templates.
  
  TEMPLATE_DEBUG in the settings.py file must be set to True"""

  #----------------------------------------------------------------------
  def __init__(self, err):
    _extensions._SubLanguageHook.__init__(self, err)
    self.__fExceptionCodeObjects = {}

  #----------------------------------------------------------------------
  def _GetMarkerFrames(self):
    """Get a list of code objects that mark entering sub-language mode,
    usually the top-level template language invocation."""
    
    code_objects = []
    try:
      django_template = sys.modules['django.template']
      code_objects.append(
        get_code(django_template.Template.render)
      )
    except:
      if kDebug:
        print("  MARKER FRAMES EMPTY")
        e, v, tb = sys.exc_info()
        print(e, v)
        traceback.print_tb(tb)
      return []

    if kDebug:
      print("  MARKER FRAMES", code_objects)
    return code_objects

  #----------------------------------------------------------------------
  def _GetModulePaths(self):
    """Get a list of paths that define what is and isn't part of the
    sub-language implementation. These are used when in sub-language mode (as
    indicated by call of _GetMarkerFrame() to determine when to stop and when
    not to stop in Python code. Returns a list of tuples (pathname, in_impl)
    where pathname is the full path and in_impl is either 0 or 1, indicating
    whether the Python code at that path is part of the sub-language
    implementation. When in_impl is 1, the debugger does not stop in Python
    code within that directory except if indicated by _GetMarkerFrames() and
    _GetSubLanguageFrames(). The list is traversed in order and first match is
    taken and its in_impl value applied to the debugger's action. The
    pathnames can either be full path directory names or *.py names."""
    
    paths = []
    try:
      django_template = sys.modules['django.template']
      dirname = os.path.dirname(os.path.dirname(django_template.__file__))
      contrib_dir = os.path.join(dirname, 'contrib')
      paths.append((os.path.join(contrib_dir, 'admin', 'templatetags', 'log'), 1))
      paths.append((os.path.join(contrib_dir, 'comments', 'templatetags', 'comments'), 1))
      paths.append((os.path.join(contrib_dir, 'webdesign', 'templatetags', 'webdesign'), 1))
      paths.append((os.path.join(contrib_dir, 'flatpages', 'templatetags', 'flatpages'), 1))
      paths.append((os.path.join(contrib_dir, 'staticfiles', 'templatetags', 'staticfiles'), 1))
      paths.append((contrib_dir, 0))
      paths.append((dirname, 1))
    except:
      if kDebug:
        print("  MODULE PATHS EMPTY")
        e, v, tb = sys.exc_info()
        print(e, v)
        traceback.print_tb(tb)
      return []
    
    if kDebug:
      print("  MODULE PATHS", paths)
    return paths

  #----------------------------------------------------------------------
  def _GetSubLanguageFrames(self):
    """Get a list of code objects for calls in the sub-language
    implementation where the debugger should call _StopHere() to determine
    if a sub-language-level breakpoint or other stop condition is reached.
    These frames are what defines the unit of stepping in the sub-language.
    This may return a partial list depending on what modules have already
    been loaded."""

    if kDebug:
      print("ENTERING _GetSubLanguageFrames")
      
    try:
      django_template = sys.modules['django.template']
    except:
      if kDebug:
        print("  SUBLANGUAGE FRAMES EMPTY")
        e, v, tb = sys.exc_info()
        print(e, v)
        traceback.print_tb(tb)
      return []
    
    def add_code_objects(scope, code_objects, django_template=django_template):
      contents = dir(scope)
      for item in contents:
        val = getattr(scope, item, None)
        try:
          if issubclass(val, django_template.Node) and hasattr(val, 'render'):
            method = getattr(val, 'render')
            code_objects.append(get_code(get_func(method)))
        except:
          pass
    
    def failure(modname):
      if kDebug:
        print("  SUBLANGUAGE FRAMES MODULE %s NOT YET IMPORTED" % modname)
        e, v, tb = sys.exc_info()
        print(e, v)
        traceback.print_tb(tb)
    
    # Some of these are not present in all Django versions but then we just skip them
    # A significant change in Django 1.9 was removing debug.template.debug
    template_modules = [
      'django.template',
      'django.template.base', 
      'django.template.debug',
      'django.template.defaulttags',
      'django.template.loader_tags', 
      'django.template.library', 
      'django.templatetags', 
      'django.templatetags.i18n', 
      'django.templatetags.l10n', 
      'django.templatetags.static', 
      'django.templatetags.tz', 
      'django.templatetags.cache', 
      'django.contrib.admin.templatetags.log', 
      'django.contrib.comments.templatetags.comments', 
      'django.contrib.webdesign.templatetags.webdesign', 
      'django.contrib.flatpages.templatetags.flatpages', 
      'django.contrib.staticfiles.templatetags.staticfiles', 
    ]
    
    code_objects = []
    for modname in template_modules:
      try:
        obj = sys.modules[modname]
        add_code_objects(obj, code_objects)
      except:
        failure(modname)
    
    try:
      # Django <= 1.8
      try:
        def get_node_from_node_list(frame):
          try:
            return None, frame.f_locals['node']
          except:
            return None, None
        django_template_debug = sys.modules['django.template.debug']
        self.__fExceptionCodeObjects[get_code(get_func(django_template_debug.DebugNodeList.render_node))] = get_node_from_node_list
        if kDebug:
          print("Django <= 1.8")
      # Django 1.9+
      except:
        django_template_base = sys.modules['django.template.base']
        def get_node_from_exception(frame):
          try:
            enclosing = frame.f_back
            obj = enclosing.f_locals['self']
            context = enclosing.f_locals['context']
            if isinstance(obj, django_template_base.Node):
              return context, obj
          except:
            pass
          return None, None
        self.__fExceptionCodeObjects[get_code(get_func(django_template_base.Template.get_exception_info))] = get_node_from_exception
        if kDebug:
          print("Django >= 1.9")
    except:
      if kDebug:
        print("  SUBLANGUAGE EXCEPTION CODE OBJECT SETUP FAILED")
        e, v, tb = sys.exc_info()
        print(e, v)
        traceback.print_tb(tb)
    if kDebug:
      print("  EXCEPTION CODE OBJECTS", self.__fExceptionCodeObjects)
      
    code_objects.extend(self.__fExceptionCodeObjects.keys())
    if kDebug:
      print("  SUB_LANGUAGE CODE OBJECTS", code_objects)
      
    return code_objects
  
  #----------------------------------------------------------------------
  def _StopHere(self, frame, event_type, action):
    """Returns True if the debugger should stop in the current stack frame.
    Only called for frames that match one of those designated in
    _GetSubLanguageFrames. Event type is the current debug tracer event: -1
    for exception, 0 for call event, 1 for line event, and 2 for return event.
    Action is the last requested debugger action: -1 to free-run until next
    breakpoint or exception, 0 to step into, 1 to step over, and 2 to step
    out."""
    
    if kDebug:
      print("  STOPHERE", frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name, event_type, action)

    # Stop on exception only in certain places
    if event_type == -1:
      if frame.f_code in self.__fExceptionCodeObjects:
        if kDebug:
          print("    stopping on exception")
        return 1
      else:
        if kDebug:
          print("    not stopping on exception")
        return 0
    
    # Stop on next call event if stepping in or over
    if event_type == 0:
      if frame.f_code in self.__fExceptionCodeObjects:
        if kDebug:
          print("  not stopping in exception code object")
        return 0
      elif action == 0 or action == 1:
        if kDebug:
          print("    stopping")
        return 1
      else:
        if kDebug:
          print("    not stopping")
        return 0
    
    # Never stop on line or return event in the sub-language impl
    if kDebug:
      print("    not stopping (line or return)")
    return 0
  
  #----------------------------------------------------------------------
  def __GetFilenameAndPosition(self, frame):

    if kDebug:
      print("ABOUT TO ACCESS FRAME", frame)

    try:
      django_template_base = sys.modules['django.template.base']
    except:
      django_template_base = None
    
    def get_template_filename(f):

      if django_template_base is None:
        return None

      while f is not None:
        try:
          template = f.f_locals.get('self', None)
          if isinstance(template, django_template_base.Template):
            return template.origin.name
        except:
          pass
        f = f.f_back
        
      return None

    # This is an exception frame
    if frame.f_code in self.__fExceptionCodeObjects:
      if kDebug:
        print("  Exception")
      context, dbg_node = self.__fExceptionCodeObjects[frame.f_code](frame)
      
    # This is regular frame
    else:
      if kDebug:
        print("  Not Exception")
      try:
        dbg_node = frame.f_locals.get('self', None)
        context = None
        try:
          # Django 1.9+
          if hasattr(dbg_node, 'token'):
            context = frame.f_locals['context']
        except:
          # Django <= 1.8
          context = None
      except:
        dbg_node = None
        context = None
        if kDebug:
          print("  Unexpected exception")
          e, v, tb = sys.exc_info()
          print(e, v)
          traceback.print_tb(tb)
        
    if kDebug:
      try:
        print("  context", context)
        print("  dbg_node", dbg_node)
      except:
        print("  failed to print context or dbg_node")
      #e, v, tb = sys.exc_info()
      #print(e, v)
      #traceback.print_tb(tb)

    if context is None and dbg_node is None:
      if kDebug:
        print("  returning now")
      return None, -1, -1, None
      
    try:
      
      # Django 1.9
      if context is not None:
        
        # In Django 1.9.3+ they put back a way to get to template filename from node
        try:
          filename = dbg_node.origin.name
          if not os.path.exists(filename):
            if kDebug:
              print("  Filename from origin does not exist", filename)
            filename = None
        except:
          if kDebug:
            print("  Failed to get filename through origin")
          filename = None
          
        # In earlier Django 1.9 we fall back to a method that doesn't work for 'extends'
        # because the data is just not there (but it covers at least a few cases)
        if filename is None:
          if kDebug:
            print("  Using fallback for template filename (does not work with 'extends')")
          filename = get_template_filename(frame)
        start, end = dbg_node.token.position
  
      # Django <=1.8
      else:
        filename = dbg_node.source[0].name
        start, end = dbg_node.source[1]

    except:
      if kDebug:
        print("  Not a debug node")
        e, v, tb = sys.exc_info()
        print(e, v)
        traceback.print_tb(tb)
        try:
          if dbg_node is not None:
            print(dir(dbg_node))
          else:
            print("  dbg_node is None")
        except:
          print("  Exception printing dir(dbg_node)")
      return None, -1, -1, None
      
    codename = str(dbg_node).replace('\n', '').replace('\r', '')
    
    if kDebug:
      print("__GETFILENAMEANDPOSITION:", filename, start, end, codename)
      
    return filename, start, end, codename
  
  #----------------------------------------------------------------------
  def _TranslateFrame(self, frame, use_positions=1):
    """Get the filename, lineno, code_line, code_name, and list of variables
    for the given frame. This is only called for those identified by
    _GetSubLanguageFrames(). When use_positions=1 (the default) then the
    lineno should be (start, end) positions. In other cases, it should be a
    line number."""

    if kDebug:
      print("  _TranslateFrame starting", frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name)
      print("  __fExceptionCodeObjects is", self.__fExceptionCodeObjects)
      
    try:
      filename, start, end, code_name = self.__GetFilenameAndPosition(frame)
      if filename is None:
        if kDebug:
          print("  filename is None in _TranslateFrame")
        return (None, -1, '', '', [])
    except:
      if kDebug:
        print("  Exception still raised after __GetFilenameAndPosition")
        e, v, tb = sys.exc_info()
        print(e, v)
        traceback.print_tb(tb)
      return (None, -1, '', '', [])
    
    if kDebug:
      print("  _TranslateFrame", filename, start, end)
     
    # Note: Need to compensate for Django converting to \n newlines and not
    # adjusting the start, end positions to match actual template file
    try:
      f = open(filename, mode='rb')
      try:
        txt = f.read()
      finally:
        f.close()
    except:
      if kDebug:
        print("  Could not open or read filename", filename)
        e, v, tb = sys.exc_info()
        print(e, v)
        traceback.print_tb(tb)
      return (None, -1, '', '', [])
      
    try:
      
      # Make this work with either Python 2 or 3
      def to_bytes(s):
        try:
          return bytes(s, 'utf-8')
        except:
          return s
        
      txtn = txt.replace(to_bytes('\r\n'), to_bytes('\n')).replace(to_bytes('\r'), to_bytes('\n'))
      while (start < end-1 and txtn[start] == to_bytes('\n')[0]):
        start += 1
      code_line = str(txtn[start:end])
       
      # XXX Optimize/cache!
      if use_positions:
        fudge = 0
        for i in range(0, start):
          if txt[i] == to_bytes('\r')[0] and i+1 < start and txt[i+1] == to_bytes('\n')[0]:
            fudge += 1
        lineno = (start+fudge, end+fudge)
      else:
        lineno = 1
        for i in range(0, start):
          if txt[i] == to_bytes('\n')[0]:
            lineno += 1
  
      # Use lower-case filenames on Windows
      if sys.platform == 'win32':
        filename = filename.lower()
        
      if kDebug:
        print("  _TranslateFrame result", filename, lineno, code_line, code_name)
        
      return (filename, lineno, code_line, code_name, [])

    except:
      if kDebug:
        print("  _TranslateFrame failed")
        e, v, tb = sys.exc_info()
        print(e, v)
        traceback.print_tb(tb)
      return (None, -1, '', '', [])
        
  #----------------------------------------------------------------------
  def _VisibleFrame(self, stack, idx):
    """Check whether the frame in given stack index should be visible to the
    user. This allows for sub-languages where recursion on the stack occurs
    within processing of a single sub-language file. _TranslateFrame should
    still translate the frame so that breakpoint can be reached but this call
    is used to remove duplicate stack frames from view. This is only called
    for frames identified by _GetSubLanguageFrames()."""

    try:

      frame, lineno = stack[idx]
    
      filename, start, end, code_name = self.__GetFilenameAndPosition(frame)
      if filename is None:
        return 0
      if sys.platform == 'win32':
        filename = filename.lower()
  
      idx += 1
      while idx < len(stack):
        f, ln = stack[idx]
        ffn, fstart, fend, fconame = self.__GetFilenameAndPosition(f)
        if ffn is None:
          # Stop at call of another template (or possibly same template recursively)
          if f.f_code in self._GetMarkerFrames():
            return 1
          idx += 1
          continue
        if sys.platform == 'win32':
          ffn = ffn.lower()
        # Prefer innermost frame for template
        if ffn == filename:
          return 0
        idx += 1
        
      # No frame for same template found further down stack
      return 1
  
    except:
      if kDebug:
        print("_VisibleFrame failed")
        e, v, tb = sys.exc_info()
        print(e, v)
        traceback.print_tb(tb)
      return 1
    
  #----------------------------------------------------------------------
  def _GetStepOutFrame(self, frame):
    """Get the frame at which the debugger should stop if a "step out"
    operation is seen in the given stack frame.  This may be called for
    both sub-language frames and regular Python frames; for the latter,
    the enclosing frame should be returned."""
      
    if kDebug:
      print("  GetStepOutFrame starting", frame.f_code.co_filename, frame.f_lineno)
  
    try:
      
      markers = self._GetMarkerFrames()
      slframes = self._GetSubLanguageFrames()
      if frame.f_code in slframes:
        fn, lineno, codeline, codename, v = self._TranslateFrame(frame)
        if kDebug:
          print("  GetStepOutFrame fn=%s" % fn)
      else:
        fn = None
        if kDebug:
          print("  GetStepOutFrame fn is None")
      
      f = frame.f_back
      last_marker_frame = frame
      while f is not None:
        if f.f_code in markers:
          if kDebug:
            print("  GetStepOutFrame in markers %s" % f.f_code.co_filename)
          last_marker_frame = f
          fn2 = self._TranslateFrame(f)[0]
          # Skip over marker frames that are not debug-enabled
          if fn2 is None:
            f = f.f_back
            continue
          if kDebug:
            print("  GetStepOutFrame fn2=%s" % str(fn2))
          if fn2 != fn:
            if kDebug:
              print("  GetStepOutFrame no file match", f.f_code.co_filename, f.f_lineno)
            return f
        else:
          if kDebug:
            print("  GetStepOutFrame in not in markers %s" % f.f_code.co_filename)
        f = f.f_back
        
      if kDebug:
        print("  GetStepOutFrame file match", last_marker_frame.f_code.co_filename, last_marker_frame.f_lineno)
      return last_marker_frame.f_back
    
    except:
      print("GetStepOutFrame failed")
      e, v, tb = sys.exc_info()
      print(e, v)
      traceback.print_tb(tb)
      return frame.f_back
    
  #----------------------------------------------------------------------
  def _GetLocals(self, frame):
    """Get the local variables for given frame.  This is only called for
    those identified by _GetSubLanguageFrames()"""

    if kDebug:
      return frame.f_locals
  
    try:
      f_locals = {}
      context = frame.f_locals['context']
      for d in context.dicts:
        try:
          f_locals.update(d)
        except:
          pass
        
      for key, value in f_locals.items():
        try:
          if str(type(value)).find('__proxy__') >= 0 and hasattr(value, 'encode'):
            f_locals[key] = value.encode('utf-8')
        except:
          pass
        
      return f_locals

    except:
      if kDebug:
        print("_GetLocals failed")
        e, v, tb = sys.exc_info()
        print(e, v)
        traceback.print_tb(tb)
        
  #----------------------------------------------------------------------
  def _GetGlobals(self, frame):
    """Get the global variables for given frame.  This is only called for
    those identified by _GetSubLanguageFrames()"""

    if kDebug:
      return frame.f_globals
    
    return {}
    
  #----------------------------------------------------------------------
  def _Eval(self, expr, frame):
    """Evaluate the given expression in the given stack frame. This is only
    called when the debugger is paused or at a breakpoint or exception.
    Returns the result of the evaluation."""

    return eval(expr, frame.f_globals, self._GetLocals(frame))
    
  #----------------------------------------------------------------------
  def _Exec(self, expr, frame):
    """Execute the given expression in the given stack frame.  This is only
    called when the debugger is paused or at a breakpoint or exception."""
    
    if expr.strip().find('\n') < 0 and expr.strip().find('\r') < 0:
      mode = 'single'
    else:
      mode = 'exec'
    code = compile(expr + '\n', '<wingdb_compile>', mode, 0, 0)
    exec(code, frame.f_globals, self._GetLocals(frame))
    
  #----------------------------------------------------------------------
  def _GetOutput(self, frame):
    raise NotImplementedError
   
  