#########################################################################
""" _qthooks.py -- Qt socket management hooks for the Wing debugger

Copyright (c) 1999-2012, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

"""
#########################################################################

import sys
import traceback

from . import _extensions

# The name of the module to watch for that indicates presence of this
# supported mainloop environment
kIndicatorModuleName = 'qt'

# The hook is activated periodically -- timeout (in milliseconds) to poll
kPollTimeout = 500


#########################################################################
# Qt-specific support for managing the debug server sockets
#########################################################################
class _SocketHook(_extensions._SocketHook):
  """ Class for managing the debug server sockets:  This is used only
  when Qt is detected as being present in the debuggee's code. """

  #----------------------------------------------------------------------
  def __init__(self, err):
    """ Constructor """
    _extensions._SocketHook.__init__(self, err)
    self.__fQtModule = None
    self.__fTimers = []
    
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

    # See if module is fully loaded
    if mod.__name__ != 'qt' or not hasattr(mod, 'libqtc') or not \
       hasattr(mod, 'QSocketNotifier'):
      self.fErr.out("NOT QT MODULE")
      return None

    # Save module reference
    self.fErr.out("FOUND QT MODULE")
    self.__fQtModule = mod
    
    # Try to register the socket
    new_sock = s
    new_sock = self._RegisterSocket(s, cb_fct)
    if new_sock == None:
      self.__fQtModule = None
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

    # See if we have what we need
    if self.__fQtModule == None:
      return None

    # CODE TO REGISTER SOCKETS: Exits app unless QApplication instance has already
    # been created and even if it has, QSocket seems to muck with the socket in a
    # way that breaks our select.select() code.  Even if we could solve that,
    # the user would only be able to use this w/o crashing by using wingdbstub
    # and placing that after the creation of the QApplication singleton (which
    # we can't seem to detect, so there's no great way to do this when code is
    # launched from the IDE).  For all of those reasons, qt support is now turned
    # off... the best plan is probably to bet on the new async debugger protocol
    # as a way to handle qt more gracefully without ending the debug session but
    # still w/o pausing reliably or being able to edit bps during free-running! [SRAD]
    
    # Try to use given module to register the socket: This fails if qt is in the
    # process of being imported outside of this call but doesn't yet have all its
    # attribs
    try:
      fileno = s.fileno()
      
      # Wrap file number in QSocket because QSocketNotifier never calls our callback
      # if we don't.  But really, we shouldn't have to do this!
      #import qtnetwork
      #qtsocket = qtnetwork.QSocket()
      #qtsocket.setSocket(fileno)
      #fileno = qtsocket.socket()

      # Set up socket notifier
      self.fErr.out("################## About to create notifier", s, "fileno=", fileno)
      method = self.__fQtModule.QSocketNotifier.Read
      self.fErr.out("################## Got method", s)
      notifier = self.__fQtModule.QSocketNotifier(fileno, method)
      self.fErr.out("################## Created notifier", s)
      notifier.connect(notifier, self.__fQtModule.SIGNAL('activated(int)'), cb_fct)
      self.fErr.out("################## Channel socket registered with Qt: ", s, cb_fct)

      return s

    # Failed but keep checking
    except:
      self.fErr.out("EXCEPTION IN QT SOCKET REGISTRATION")
      t, val, tb = sys.exc_info()
      self.fErr.out("Runtime failure details:")
      self.fErr.out("Exception:", t)
      self.fErr.out("Value =", val)
      self.fErr.out("Traceback:")
      tbf = traceback.format_tb(tb)
      for item in tbf:
        self.fErr.out(item)

      self.fErr.out("################## 'qt' module not fully loaded")
      return None

    # CODE TO POLL INSTEAD OF REGISTERING SOCKETS:  This doesn't work because QT
    # fails to call the callback except when the QTimer is created and started
    # in certain contexts (like at the top level before the mainloop is started).
    # Most likely, we're doing this too early, although tests outside of the
    # debugger show that it also doesn't work in code after qt is definately
    # initialized and before the mainloop is started, if that code is in 
    # a class constructor.  This is just too weird to rely on! [SRAD]
    
    ## Set up timer for socket polling
    #try:
      #timer = self.__fQtModule.QTimer()
      #def test(*args):
        #self.fErr.out("SOCKET TIMER", args)
      #timer.connect(timer, self.__fQtModule.SIGNAL('timeout()'), test)
      #timer.start(kPollTimeout, 0)
  
      #self.fErr.out("################## Timer for polling socket registered with Qt: ", s)
      #self.__fTimers.append(timer)
          
      #return s
    
    #except:
      #self.fErr.out("EXCEPTION IN QT SOCKET REGISTRATION")
      #t, val, tb = sys.exc_info()
      #self.fErr.out("Runtime failure details:")
      #self.fErr.out("Exception:", t)
      #self.fErr.out("Value =", val)
      #self.fErr.out("Traceback:")
      #tbf = traceback.format_tb(tb)
      #for item in tbf:
        #self.fErr.out(item)

      #self.fErr.out("################## 'qt' module not fully loaded")
      #return None

  #----------------------------------------------------------------------
  def _UnregisterSocket(self, s):
    """ Function to unregister a socket with the supported environment.
    The socket passed in should be the one returned from _Setup() or
    _RegisterSocket(). """    
    
    self.fErr.out("################ Deregistered socket with Qt: ", s)
    pass  # Unimplemented [SRAD]

