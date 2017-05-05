#########################################################################
""" _gtkhooks.py -- Gtk socket management hooks for the Wing debugger

Copyright (c) 1999-2012, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

"""
#########################################################################

from . import _extensions

# The name of the module to watch for that indicates presence of this
# supported mainloop environment
kIndicatorModuleName = ['gtk', 'gobject']


#########################################################################
# GTK-specific support for managing the debug server sockets
#########################################################################
class _SocketHook(_extensions._SocketHook):
  """ Class for managing the debug server sockets:  This is used only
  when gtk is detected as being present in the debuggee's code. """

  #----------------------------------------------------------------------
  def __init__(self, err):
    """ Constructor """
    _extensions._SocketHook.__init__(self, err)
    self.__fHandlers = {}
    self.__fModule = None
    
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
    
    # Check if module is fully loaded as far as the constructs we will need
    if mod.__name__ == 'gtk':
      if not hasattr(mod, 'input_add') or not hasattr(mod, 'input_remove'):
        return None
      if hasattr(mod, 'GDK'):
        gdk_mod = mod.GDK
      elif hasattr(mod, 'gdk'):
        gdk_mod = mod.gdk
      else:
        return None
      if not hasattr(gdk_mod, 'INPUT_READ') \
         or not hasattr(gdk_mod, 'INPUT_EXCEPTION'):
        return None
    elif mod.__name__ == 'gobject':
      for attrib in ['io_add_watch', 'source_remove', 'IO_IN', 'IO_ERR']:
        if not hasattr(mod, attrib):
          return None
    else:
      return None
    
    # Try to register the first socket
    self.__fModule = mod
    new_sock = self._RegisterSocket(s, cb_fct)
    if new_sock == None:
      self.__fModule = None
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

    # Try to use given module to register the socket:  This may still fail
    # if module is in the process of being imported
    try:
      
      # Register with GTK
      if self.__fModule.__name__ == 'gobject':
        cond = self.__fModule.IO_IN | self.__fModule.IO_ERR
      elif hasattr(self.__fModule, 'GDK'):
        cond = self.__fModule.GDK.INPUT_READ | self.__fModule.GDK.INPUT_EXCEPTION
      else:
        cond = self.__fModule.gdk.INPUT_READ | self.__fModule.gdk.INPUT_EXCEPTION

      if self.__fModule.__name__ == 'gobject':
        handler_id = self.__fModule.io_add_watch(s, cond, cb_fct)
      else:
        handler_id = self.__fModule.input_add(s, cond, cb_fct)
      self.__fHandlers[s] = handler_id
      
      # Done
      self.fErr.out("################## Socket registered with gtk: ", s)
      return s

    # Failed but will keep checking
    except:
      self.fErr.out("################## 'gtk' module not fully loaded")
      return None
    
  #----------------------------------------------------------------------
  def _UnregisterSocket(self, s):
    """ Function to unregister a socket with the supported environment.
    The socket passed in should be the one returned from _Setup() or
    _RegisterSocket(). """    

    self.fErr.out("################ Deregistered socket with gtk: ", s)
    if self.__fModule.__name__ == 'gobject':
      self.__fModule.source_remove(self.__fHandlers[s])
    else:
      self.__fModule.input_remove(self.__fHandlers[s])
    del self.__fHandlers[s]

  #----------------------------------------------------------------------
  def _ProcessEvents(self):
    """ Method to process gui events if possible. """
    
    # XXX Never called currently
    
    if self.__fModule.__name__ == 'gtk':
      while self.__fModule.events_pending():
        self.__fModule.main_iteration()
    else:
      ctx = self.__fModule.main_context_default()
      while ctx.pending():
        ctx.iteration()
