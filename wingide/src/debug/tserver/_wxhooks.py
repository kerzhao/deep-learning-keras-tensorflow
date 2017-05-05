#########################################################################
""" _wxhooks.py -- wxPython socket management hooks for the Wing debugger

Copyright (c) 1999-2012, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

"""
#########################################################################

from . import _extensions

import sys
import traceback
import types

if sys.hexversion < 0x03000000:
  import new

# The name of the module to watch for that indicates presence of this
# supported mainloop environment
kIndicatorModuleName = 'wxPython.wx'

# The hook is activated periodically -- timeout (in milliseconds) to poll
kPollTimeout = 500

def iscallable(x):
  if sys.hexversion >= 0x03000000:
    return hasattr(x, '__call__')
  else:
    return callable(x)

#########################################################################
# wxPython-specific support for managing the debug server sockets
#########################################################################
class _SocketHook(_extensions._SocketHook):
  """ Class for managing the debug server sockets:  This is used only
  when wxPython is detected as being present in the debuggee's code. """

  _kTimerClassName = 'wxTimer'
  _kAppClassName = 'wxApp'
  _kGetAppFunctionName = 'wxGetApp'
  _kIndicatorModuleName = kIndicatorModuleName
  
  #----------------------------------------------------------------------
  def __init__(self, err):
    """ Constructor """
    _extensions._SocketHook.__init__(self, err)
    self.__fWxModule = None
    self.__fTimer = None
    self.__fTimerStarted = 0
    self.__fRealMainLoop = None
    
  #-----------------------------------------------------------------------
  def _ValidClass(self, c):
    if sys.hexversion >= 0x03000000:
      return type(c) is type
    else:
      return isinstance(c, types.ClassType)
        
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
    if mod.__name__ != self._kIndicatorModuleName:
      return None

    # Try to register the first socket
    self.__fWxModule = mod
    new_sock = self._RegisterSocket(s, cb_fct)
    if new_sock == None:
      self.__fWxModule = None
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

    # Try to use given module to setup timeout
    try:
      if self.__fWxModule is None:
        return None
      
      # Could disable this in wx > 3.0 because it's no longer needed (Python
      # code is apparently always called)
      #ver = getattr(self.__fWxModule, '__version__', None)
      #if ver is not None:
        #ver_tup = ver.split('.')
        #try:
          #ver_tup = [int(v) for v in ver_tup]
          #while len(ver_tup) < 4:
            #ver_tup.append(0)
          #ver_tup = tuple(ver_tup)
        #except:
          #ver_tup = (2, 5, 0, 0)
        #if ver_tup >= (3, 0, 0, 0):
          #return s
              
      timer_class = getattr(self.__fWxModule, self._kTimerClassName, None)
      if not self._ValidClass(timer_class):
        return None
      app_class = getattr(self.__fWxModule, self._kAppClassName, None)
      if not self._ValidClass(app_class):
        return None
      get_app_function = getattr(self.__fWxModule, self._kGetAppFunctionName, None)
      if not iscallable(get_app_function):
        return None

      # Replace MainLoop with our own wrapper method
      if self.__fRealMainLoop is None:
        self.__fRealMainLoop = app_class.MainLoop
        if sys.hexversion < 0x03000000:
          app_class.MainLoop = new.instancemethod(self.__MainLoopWrapper, None, app_class)
        else:
          app_class.MainLoop = types.MethodType(self.__MainLoopWrapper, app_class)
      
      # Start the timer immediately if there is already an app
      if get_app_function() is not None:
        self.__CreateTimerIfNeeded()
        if self.__fTimer is not None:
          self.__fTimer.Start(kPollTimeout, 0)
          self.__fTimerStarted = True

      self.fErr.out("################## Timer for polling socket registered with wxPython: ", s)
      self.__fCallBack = cb_fct
      
      return s

    # Failed but keep checking
    except:
      traceback.print_exc()
      self.fErr.out("################## 'wxPython' module not fully loaded")
      return None
    
  #----------------------------------------------------------------------
  def _UnregisterSocket(self, s):
    """ Function to unregister a socket with the supported environment.
    The socket passed in should be the one returned from _Setup() or
    _RegisterSocket(). """    

    if self.__fTimer is not None and self.__fTimerStarted:
      self.__fTimer.Stop()
    self.__fTimerStarted = 0
    self.__fTimer = None
    self.fErr.out("################ Deregistered socket with wxPython: ", s)

  #----------------------------------------------------------------------
  def __MainLoopWrapper(self, app_self, *args, **kw):
    """ Starts timer before the mainloop if it hasn't been started already. """

    self.__CreateTimerIfNeeded()
    if self.__fTimer is not None and not self.__fTimerStarted:
      self.__fTimer.Start(kPollTimeout, 0)
    args = (app_self,) + tuple(args)
    if sys.hexversion >= 0x03000000:
      return self.__fRealMainLoop(*args, **kw)
    else:
      return apply(self.__fRealMainLoop, args, kw)

  #----------------------------------------------------------------------
  def __TimerCallback(self, id = None):
    """ Method used as timer callback when polling is used. """
    
    if iscallable(self.__fCallBack):
      try:
        self.__fCallBack()
      except:
        self.fErr.out("################## Exception occurred in socket checking function")

  #----------------------------------------------------------------------
  def __CreateTimerIfNeeded(self):
    """ Creates timer; should be called after app is created. """
    
    if self.__fTimer is not None:
      return
    
    timer_class = getattr(self.__fWxModule, self._kTimerClassName, None)
    if not self._ValidClass(timer_class):
      return

    # Create a wxPython timer -- derive a class at runtime because we
    #  don't have access to the base class until now
    class CTimerAdapter(timer_class):
      def Notify(self):
        self._fCallback()
    self.__fTimer = CTimerAdapter()
    self.__fTimer._fCallback = self.__TimerCallback
