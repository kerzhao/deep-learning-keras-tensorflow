#########################################################################
""" _tkinterhooks.py -- Tkinter socket management hooks for the Wing debugger

Copyright (c) 1999-2012, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

"""
#########################################################################

from . import _extensions
import sys

# The name of the module to watch for that indicates presence of this
# supported mainloop environment
kIndicatorModuleName = '_tkinter'

# The hook is either activated when a network event is available or 
# periodically -- on win32, createfilehandler is unavailable so the
# hook needs to be polled.

# Whether to use createfilehandler if it's not None.
kUseCreateFileHandler = 1

# Timeout (in milliseconds) if we need to poll
kPollTimeout = 5000

def iscallable(x):
  if sys.hexversion >= 0x03000000:
    return hasattr(x, '__call__')
  else:
    return callable(x)

#########################################################################
# Tkinter-specific support for managing the debug server sockets
#########################################################################
class _SocketHook(_extensions._SocketHook):
  """ Class for managing the debug server sockets:  This is used only
  when Tkinter is detected as being present in the debuggee's code. """

  #----------------------------------------------------------------------
  def __init__(self, err):
    """ Constructor """
    _extensions._SocketHook.__init__(self, err)
    self.__fTkinterModule = None
    self.__fCallBack = None
    
  #-----------------------------------------------------------------------
  def _Setup(self, mod, s, cb_fct):
    """ Attempt to set up socket registration with the given module
    reference : This should be a reference to the indicator module
    for the supported environment.  The first socket is registered 
    with given action callback via _RegisterSocket().  Returns the
    socket if succeeded or None if fails (e.g. because the module is 
    not yet fully loaded and we cannot yet use it to start registering 
    sockets.  Note that the returned socket may be different than the
    socket passed in because some environments require a wrapper:  The
    returned socket is then used in place of the original in the
    debug server code. """
    
    # Check if we can pull this off now (if not, we keep trying)
    if mod.__name__ != kIndicatorModuleName:
      return None

    # Try to register the first socket
    self.__fTkinterModule = mod
    new_sock = self._RegisterSocket(s, cb_fct)
    if new_sock == None:
      self.__fTkinterModule = None
      return None
    
    # Success
    return new_sock
  
  #----------------------------------------------------------------------
  def _RegisterSocket(self, s, cb_fct):
    """ Function to register a socket with a mainloop: Subsequently the given
    callback function is called whenever there is data to be read on the
    socket.  Returns the socket if succeeded; None if fails. As in _Setup(),
    the returned socket may differ from the one passed in, in which case
    the debug server will substitute the socket that is used in its code."""

    # Try to use given module to register the socket:  This fails if
    # gtk is in the process of being imported outside of this
    # call but doesn't yet have all its attribs.
    try:
      if kUseCreateFileHandler \
         and hasattr(self.__fTkinterModule, 'createfilehandler') \
         and iscallable(self.__fTkinterModule.createfilehandler):
        cond = self.__fTkinterModule.READABLE | self.__fTkinterModule.EXCEPTION
        self.__fTkinterModule.createfilehandler(s, cond, cb_fct)
      else:
        self.__fTkinterModule.createtimerhandler(kPollTimeout, self.__TimerCallback)
        
      self.fErr.out("################## Channel socket registered with Tkinter: ", s)
      self.__fCallBack = cb_fct
      
      return s

    # Failed but keep checking
    except:
      self.fErr.out("################## 'Tkinter' module not fully loaded")
      return None
    
  #----------------------------------------------------------------------
  def _UnregisterSocket(self, s):
    """ Function to unregister a socket with the supported environment.
    The socket passed in should be the one returned from _Setup() or
    _RegisterSocket(). """    
    
    self.fErr.out("################ Deregistered socket with Tkinter: ", s)
    pass  # Unimplemented [SRAD]

  #----------------------------------------------------------------------
  def __TimerCallback(self):
    """ Method used as timer callback when polling is used. """
    
    if iscallable(self.__fCallBack):
      try:
        self.__fCallBack()
      except:
        self.fErr.out("################## Exception occurred in socket checking function")

    # Install a new timer
    self.__fTkinterModule.createtimerhandler(kPollTimeout, self.__TimerCallback)
