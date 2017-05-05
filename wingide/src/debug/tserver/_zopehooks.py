#########################################################################
""" _zopehooks.py -- Zope socket management hooks for the Wing debugger

Copyright (c) 1999-2012, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

"""
#########################################################################

import traceback

from . import _extensions

# The name of the module to watch for that indicates presence of this
# supported mainloop environment
kIndicatorModuleName = 'ZServer'

# Pretend that this is a top-level module by setting __package__ to '' so that
# imports executed after sys.modules is reset don't emit a runtime warning due 
# to debug.tserver can no longer be found.  
# Note that relative imports cannot be used after this
__package__ = ''

#########################################################################
# Zope-specific support for managing the debug server sockets
#########################################################################
class _SocketHook(_extensions._SocketHook):
  """ Class for managing the debug server sockets:  This is used only
  when Zope is detected as being present in the debuggee's code. """

  #----------------------------------------------------------------------
  def __init__(self, err):
    """ Constructor """
    _extensions._SocketHook.__init__(self, err)
    
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
    
    # Just try to register the first socket; no extra tests needed
    new_sock = self._RegisterSocket(s, cb_fct)
    return new_sock
  
  #----------------------------------------------------------------------
  def _RegisterSocket(self, s, cb_fct):
    """ Function to register a socket with a mainloop: Subsequently the given
    callback function is called whenever there is data to be read on the
    socket.  Returns the socket if succeeded; None if fails. As in _Setup(),
    the returned socket may differ from the one passed in, in which case
    the debug server will substitute the socket that is used in its code."""

    # Try to load Zope modules:  May fail early in run
    try:
      import asyncore
      self.fErr.out("################## Imported asyncore from Zope:")
      self.fErr.out(asyncore.__file__)
    except:
      self.fErr.out("################## Unable to import asyncore in Zope process")
      return None

    # Try to use modules to register the socket:  This fails if
    # Zope is in the process of being imported outside of this
    # call but doesn't yet have all its attribs.
    try:
      disp = asyncore.dispatcher(sock=s)
      def null_fct():
        pass
      def false_fct():
        return 0
      disp.handle_read = cb_fct
      disp.handle_error = cb_fct
      disp.handle_expt = cb_fct
      disp.handle_write = null_fct
      disp.handle_connect = null_fct
      disp.handle_accept = null_fct
      disp.handle_close = null_fct
      # Disable select for write
      disp.writable = false_fct
      # Set socket to blocking
      try:
        # This works in Zope 2.2.2, and seems required there (?) [SRAD]
        disp.set_blocking(1)
      except:
        # This is how it would be done in Zope 2.3.0 but there it breaks
        # attach/detach/reattach and other things! [SRAD]
        # disp.socket.setblocking(1)
        pass
      self.fErr.out("################## Channel socket registered with Zope")
      return disp

    # Failed but keep checking
    except:
      self.fErr.out("################## Zope asyncore registration failed")
      traceback.print_exc()
      return None

  #----------------------------------------------------------------------
  def _UnregisterSocket(self, s):
    """ Function to unregister a socket with the supported environment.
    The socket passed in should be the one returned from _Setup() or
    _RegisterSocket(). """
    
    self.fErr.out("################ Deregistered socket with Zope: ", s)
    # Should just work:  When the socket is closed, asyncore deregisters it

