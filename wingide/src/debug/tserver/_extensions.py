#########################################################################
""" _extensions.py -- Lists the modules to import debugger extensions

Copyright (c) 1999-2012, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

This module enumerates the supported extensions for the debugger.  There
are three types of extensions:

(1) Extensions that support particular mainloop environments so the debug
server can register its communication sockets in order to more reliably
service those sockets.

(2) Extensions that support particular sub-languages such as templating
languages, so that the sub-language files can be debugged.

(3) Extensions that support execution of a guest event loop during times
when the debugger is in control, such as when in the Exec call.  These
extensions both service the guest event loop and may alter it to prevent
interactively typed commands from hanging up in the event loop.

Mainloops
---------

To add your own mainloop environment to the supported list, you need to:

(1) Write a module that implements the necessary hooks for registering
    a socket in the environment.  The module must contain the following 
    at the top level scope:
  
    (a) kIndicatorModuleName : A string containing the name of the module
    whose import indicates that your supported mainloop environment is
    present in the debug program (or a list of such names)  E.g., for 
    gtk this is 'gtk', and for Zope this is 'ZServer'.

    (b) _SocketHook : A class that implements support for registering
    and deregistering sockets with your mainloop environment.  This is
    a descendent of the class _SocketHook defined below.

(2) Place this module into this directory (src/debug/tserver)

(3) Add your module's name to the list below

Sub-Languages
-------------

To add your own sub-language support, you need to:

(1) Write a module that implements the necessary hooks for the particular
    language.  The module must contain the following at the top level scope:
  
    (a) kIndicatorModuleName : A string containing the name of the module
    whose import indicates that your supported sub-language is present 
    in the debug program (or a list of such names).  E.g., for Django 
    templates this is 'django.template'.

    (b) _SubLanguageHook : A class that implements stack conversion, obtaining
    locals and globals, evaluating, executing, and introspecting in sub-language
    stack frames, obtaining output, etc.  This is a descendent of the class 
    _SubLanguageHook defined below.

(2) Place this module into this directory (src/debug/tserver)

(3) Add your module's name to the list below

Exec Helpers
------------

To add your own exec helper to keep a guest mainloop active, you need to:

(1) Write a module that implements a subclass of _ExecHelper.  This module
should contain kIndicatorModuleName at the top level at for the other
types of extensions above.

(2) Place this module into this directory (src/debug/tserver)

(3) Add your module's name to the list below

Notes
-----

The debugger supports many Python versions.  As such, the extensions implemented
must at least import in each Python version back to and including 2.0 and also
Python 3.x.

As of Wing 6, the debugger server code is imported as the debug.tserver python
package.  After the code loads, this package is removed from sys.modules so it's
hidden from the code being debugged, which works well.  A hitch, though, is that
import statements executed after debug.tserver is removed from sys.modules --
in a function called after the debugger is initialized, for example -- will
print a warning.  The way around this is to set __package__ = '' global variable 
in the top level of the module.  This causes the module to be treated as a top
level module and avoids the code path that prints the warning.  Relative imports 
will not work after __package__ = '' is executed

"""
#########################################################################

# Add your extension to the appropriate list
kSupportedMainloops = [ 
  '_gtkhooks', '_zopehooks', '_tkinterhooks', '_wxhooks', '_wx25hooks' 
]
kSupportedSubLanguages = [ 
  '_django', 
]
kSupportedExecHelpers = [
  '_matplotlib',
]


#########################################################################
# Abstract class for managing the debug server sockets
#########################################################################
class _SocketHook:
  """ Class for managing the debug server sockets:  Descendents implement
  registering sockets with resident mainloop environments in order to
  cause them to be serviced more reliably.  This class is defined only
  to document what is required of mainloop extension modules."""

  #----------------------------------------------------------------------
  def __init__(self, err):
    """ Constructor : err is the error output stream, which has a single
    method 'out' that acts like Python's 'print' command (but with normal
    function syntax, accepting 1 or more comma separated args).  This
    can be used to ` messages during debugging your environment
    support and will remain silent unless the verbose debugging option
    is turned on. """
    
    self.fErr = err
    
  #-----------------------------------------------------------------------
  def _Setup(self, mod, s, cb_fct):
    """ Attempt to set up socket registration with the given module
    reference : This should be a reference to the indicator module
    for the supported environment.  The first socket is registered 
    with given action callback via _RegisterSocket().  Returns the
    socket if succeeded or None if fails (e.g. because the module is 
    not yet fully loaded and we cannot yet use it to start registering 
    sockets).  Note that the returned socket may be different than the
    socket passed in because some environments require a wrapper:  The
    returned socket is then used in place of the original in the
    debug server code. """
    pass
    
  #----------------------------------------------------------------------
  def _RegisterSocket(self, s, cb_fct):
    """ Function to register a socket with a mainloop: Subsequently the given
    callback function is called whenever there is data to be read on the
    socket.  Returns the socket if succeeded; None if fails. As in _Setup(),
    the returned socket may differ from the one passed in, in which case
    the debug server will substitute the socket that is used in its code."""
    pass
    
  #----------------------------------------------------------------------
  def _UnregisterSocket(self, s):
    """ Function to unregister a socket with the supported environment.
    The socket passed in should be the one returned from _Setup() or
    _RegisterSocket(). """    
    pass

  
########################################################################
class _SubLanguageHook:
  """Class for adding a sub-language such as a templating language to the
  debugger. It allows the debugger to synthesize stack frames belonging to the
  sub-language, and to determine when a breakpoint is reached, obtain
  locals/globals, and evaluate, execute, or introspect in the contents of a
  synthesized stack frame. All functionality is in sub-classes; this class
  exists only to document the API.
  
  Implementation note:  Typically, the methods here should not import modules
  but should just refer to already-loaded modules via sys.modules.  Otherwise,
  import order problems can be provoked.  """

  #----------------------------------------------------------------------
  def __init__(self, err):
    """ Constructor : err is the error output stream, which has a single
    method 'out' that acts like Python's 'print' command (but with normal
    function syntax, accepting 1 or more comma separated args).  This
    can be used to ` messages during debugging your environment
    support and will remain silent unless the verbose debugging option
    is turned on. """
    
    self.fErr = err
    
  #----------------------------------------------------------------------
  def _GetMarkerFrames(self):
    """Get a list of code objects that mark entering sub-language mode,
    usually the top-level template language invocation."""

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

  #----------------------------------------------------------------------
  def _GetSubLanguageFrames(self):
    """Get a list of code objects for calls in the sub-language
    implementation where the debugger should call _StopHere() to determine
    if a sub-language-level breakpoint or other stop condition is reached.
    These frames are what defines the unit of stepping in the sub-language.
    This may return a partial list depending on what modules have already
    been loaded."""

  #----------------------------------------------------------------------
  def _StopHere(self, frame, event_type, action):
    """Returns True if the debugger should stop in the current stack frame.
    Only called for frames that match one of those designated in
    _GetSubLanguageFrames. Event type is the current debug tracer event: -1
    for exception, 0 for call event, 1 for line event, and 2 for return event.
    Action is the last requested debugger action: -1 to free-run until next
    breakpoint or exception, 0 to step into, 1 to step over, and 2 to step
    out."""
    
  #----------------------------------------------------------------------
  def _TranslateFrame(self, frame, use_positions=1):
    """Get the filename, lineno, code_line, code_name, and list of variables
    for the given frame. This is only called for those identified by
    _GetSubLanguageFrames(). When use_positions=1 (the default) then the
    lineno should be (start, end) positions. In other cases, it should be a
    line number."""

  #----------------------------------------------------------------------
  def _VisibleFrame(self, stack, idx):
    """Check whether the frame in given stack index should be visible to the
    user. This allows for sub-languages where recursion on the stack occurs
    within processing of a single sub-language file. _TranslateFrame should
    still translate the frame so that breakpoint can be reached but this call
    is used to remove duplicate stack frames from view. This is only called
    for frames identified by _GetSubLanguageFrames()."""

  #----------------------------------------------------------------------
  def _GetStepOutFrame(self, frame):
    """Get the frame at which the debugger should stop if a "step out"
    operation is seen in the given stack frame.  This may be called for
    both sub-language frames and regular Python frames; for the latter,
    the enclosing frame should be returned."""

  #----------------------------------------------------------------------
  def _GetLocals(self, frame):
    """Get the local variables for given frame.  This is only called for
    those identified by _GetSubLanguageFrames()"""
    
  #----------------------------------------------------------------------
  def _GetGlobals(self, frame):
    """Get the global variables for given frame.  This is only called for
    those identified by _GetSubLanguageFrames()"""
    
  #----------------------------------------------------------------------
  def _Eval(self, expr, frame):
    """Evaluate the given expression in the given stack frame. This is only
    called when the debugger is paused or at a breakpoint or exception.
    Returns the result of the evaluation."""

  #----------------------------------------------------------------------
  def _Exec(self, expr, frame):
    """Execute the given expression in the given stack frame.  This is only
    called when the debugger is paused or at a breakpoint or exception."""
    
  #----------------------------------------------------------------------
  def _Introspect(self, expr, frame):
    raise NotImplementedError

  #----------------------------------------------------------------------
  def _GetOutput(self, frame):
    raise NotImplementedError
   
  
########################################################################
class _ExecHelper(object):
  """Class for adding helpers that are called before and after execution of
  commands via Exec, to deal with issues affecting interactive use of 
  certain modules, and periodically to service a guest event loop when the
  debugger is in control.  Should define three methods:
  
  def Prepare(self) -- Called before Exec action
  def Cleanup(self) -- Called after Exec action
  def Update(self) -- Called periodically when the helper is activated
  
  """
  
  pass


  
  