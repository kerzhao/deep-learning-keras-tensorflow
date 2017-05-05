""" _matplotlib.py -- Plugin for working w/ matplotlib and pylab

Copyright (c) 1999-2015, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

"""

import sys
from . import _extensions

kIndicatorModuleName = ('pylab', 'matplotlib')

# Pretend that this is a top-level module by setting __package__ to '' so that
# imports executed after sys.modules is reset don't emit a runtime warning due 
# to debug.tserver can no longer be found.  
# Note that relative imports cannot be used after this
__package__ = ''

kDebug = 0
       
def get_wx_core():
  import wx
  try:
    return wx._core_
  except:
    pass
  try:
    return wx._core
  except:
    return None

class _ExecHelper(_extensions._ExecHelper):

  _fOriginalUse = None
  
  _fSingleton = None
  
  def __new__(cls):
    """ New method to create and then always return a singleton.  It also may
    raise a RuntimeError in some cases, but the create singleton is still kept
    for reuse. """
  
    if cls._fSingleton is None:
      cls._fSingleton = object.__new__(cls)
      
    self = cls._fSingleton
    self.Setup()
    return self
  
  def Setup(self):
    """ Set up the helper; this will raise RuntimError in some situations
    if it isn't ready. """

    if kDebug:
      print("Activating matplotlib helper")
      
    import matplotlib
    if not hasattr(matplotlib, 'use') or not hasattr(matplotlib, 'get_backend'):
      # Try again later
      if kDebug:
        print("No use or get_backend... waiting for import to complete")
      raise RuntimeError()
    self.__fMatplotlib = matplotlib
    
    # Wrap matplotlib.use iff it hasn't been wrapped before
    if self._fOriginalUse is None:
      self._fOriginalUse = matplotlib.use
      
      def wrap_use(*args, **kw):
        if kDebug:
          print("wrap_use called")
        self._fOriginalUse(*args, **kw)
        try:
          self.__ChangeBackend()
        except RuntimeError:
          if kDebug:
            print("Failed to track backend change")
      matplotlib.use = wrap_use
    
    self.__fPendingCleanup = None
    self.__fInitialShow = 0
    
    self.__ChangeBackend()
    
    if kDebug:
      print("Success activating matplotlib helper")
    
  def __ChangeBackend(self):
    
    if kDebug:
      print("__ChangeBackend")

    had_cleanup_pending = bool(self.__fPendingCleanup)
    if self.__fPendingCleanup:
      if kDebug:
        print("Calling pending cleanup...")
      self.__fPendingCleanup()
      self.__fPendingCleanup = None
      
    self.__fBackend = self.__fMatplotlib.get_backend()
    if kDebug:
      print("Backend: ", self.__fBackend)
    
    self.Prepare = self.__Noop
    self.Cleanup = self.__Noop
    self.Update = self.__Noop
    
    if self.__fBackend == 'TkAgg':
      try:
        import Tkinter
      except ImportError:
        try:
          import tkinter as Tkinter
        except ImportError:
          Tkinter = None
          if kDebug:
            print("Failed to import Tkinter or tkinter")
      if Tkinter is not None:
        self.__fTkinter = Tkinter
        self.__fSavedMainloop = Tkinter.mainloop
        self.__fSavedMiscMainloop = Tkinter.Misc.mainloop
        self.Prepare = self.__TkPrepare
        self.Cleanup = self.__TkCleanup
        self.Update = self.__TkUpdate

    elif self.__fBackend == 'Qt4Agg':
      try:
        from PyQt4 import QtGui
        from PyQt4 import QtCore
      except ImportError:
        try:
          from PySide import QtGui
          from PySide import QtCore
        except ImportError:
          if kDebug:
            print("Unexpected failure to import PyQt4 or PySide")
          return
      self.__fQtGui = QtGui
      self.__fQtCore = QtCore
      try:
        self.__fSavedqAppMainloop = getattr(QtGui.qApp, 'exec_', None)
        self.__fSavedQApplicationMainloop = QtGui.QApplication.exec_
        self.__fSavedQCoreMainloop = QtCore.QCoreApplication.exec_
      except AttributeError:
        if kDebug:
          print("Too early -- waiting for imports to complete")
        raise RuntimeError()
      self.Prepare = self.__Qt4Prepare
      self.Cleanup = self.__Qt4Cleanup
      self.Update = self.__Qt4Update
      
    elif self.__fBackend == 'GTKAgg' or self.__fBackend == 'GTKCairo':
      try:
        import gtk
      except ImportError:
        pass
      else:
        self.__fGTK = gtk
        self.__fSavedGTKMainloop = gtk.mainloop
        self.__fSavedGTKMain = gtk.main
        self.Prepare = self.__GtkPrepare
        self.Cleanup = self.__GtkCleanup
        self.Update = self.__GtkUpdate
    
    elif self.__fBackend == 'WXAgg':
      try:
        import wx
      except ImportError:
        pass
      else:
        self.__fWX = wx      
        self.__fWXCore = get_wx_core()
        if self.__fWXCore is not None:
          self.__fWxEventloop = wx.EventLoop()
          self.Prepare = self.__WxPrepare
          self.Cleanup = self.__WxCleanup
          self.Update = self.__WxUpdate
        
    elif self.__fBackend == 'MacOSX':
      if self.__fMatplotlib.__version__ < '1.1.0':
        pass
      else:
        mp = sys.modules.get('matplotlib')
        try:
          be = getattr(mp, 'backends')
          be = getattr(be, 'backend_macosx')
          show = getattr(be, 'show')
        except AttributeError:
          if kDebug:
            print("Too early -- waiting for imports to complete")
          raise RuntimeError()
        self.__fMacOSX_Show = show
        self.__fMacOSX_Mainloop = self.__fMacOSX_Show.mainloop
        self.Prepare = self.__MacOSXPrepare
        self.Cleanup = self.__MacOSXCleanup
        self.Update = self.__MacOSXUpdate
        
    if had_cleanup_pending:
      self.Prepare()
        
  def __TkPrepare(self):
    if kDebug:
      print("__TkPrepare")
    self.__fTkinter.mainloop = self.__Noop
    self.__fTkinter.Misc.mainloop = self.__Noop
    self.__fWasInteractive = self.__fMatplotlib.is_interactive()
    self.__fMatplotlib.interactive(True)
    self.__fPendingCleanup = self.__TkCleanup
    
  def __TkUpdate(self):
    
    if kDebug:
      print("__TkUpdate")
      
    # Do not attempt to update when there are no windows (causes X11 errors)
    # XXX Not a good idea as it uses undocumented API but there is no
    # XXX alternative.  This means support will break if matplotlib removes
    # XXX this in the future but there's not much we can do.
    try:
      if not self.__fMatplotlib._pylab_helpers.Gcf.get_all_fig_managers():
        if kDebug:
          print("  no plots")
        return
    except:
      if kDebug:
        print("  exception")
      return
    
    # This only works in the main thread in Tk
    top = None
    try:
      try:
        top = self.__fTkinter.Tk()
        top.withdraw()
      except:
        if kDebug:
          import traceback
          traceback.print_exc()
        try:
          top.destroy()
          top = None
        except:
          top = None
      if top is not None:
        top.update()
        top.destroy()
    except:
      if kDebug:
        import traceback
        traceback.print_exc()
    
  def __TkCleanup(self):
    if kDebug:
      print("__TkCleanup")
    self.__fPendingCleanup = None
    self.__fTkinter.mainloop = self.__fSavedMainloop
    self.__fTkinter.Misc.mainloop = self.__fSavedMiscMainloop
    self.__fMatplotlib.interactive(self.__fWasInteractive)
    
  def __Qt4Prepare(self):
    if kDebug:
      print ("__Qt4Prepare")
    if self.__fSavedqAppMainloop is not None:
      self.__fQtGui.qApp.exec_ = self.__Noop
    self.__fQtGui.QApplication.exec_ = self.__Noop
    self.__fQtCore.QCoreApplication.exec_ = self.__Noop
    try:
      self.__fQtCore.pyqtRemoveInputHook()    
    except:
      pass
    self.__fWasInteractive = self.__fMatplotlib.is_interactive()
    self.__fMatplotlib.interactive(True)
    self.__fPendingCleanup = self.__Qt4Cleanup
    
  def __Qt4Cleanup(self):
    if kDebug:
      print ("__Qt4Cleanup")
    self.__fPendingCleanup = None
    if self.__fSavedqAppMainloop is not None:
      self.__fQtGui.qApp.exec_ = self.__fSavedqAppMainloop
    self.__fQtGui.QApplication.exec_ = self.__fSavedQApplicationMainloop
    self.__fQtCore.QCoreApplication.exec_ = self.__fSavedQCoreMainloop
    try:
      self.__fQtCore.pyqtRestoreInputHook()    
    except:
      pass
    self.__fMatplotlib.interactive(self.__fWasInteractive)
    
  def __Qt4Update(self):
    if kDebug:
      print("__Qt4Update")
    self.__fQtGui.QApplication.processEvents()
    
  def __GtkPrepare(self):
    if kDebug:
      print ("__GtkPrepare")
    self.__fGTK.mainloop = self.__Noop
    self.__fGTK.main = self.__Noop
    self.__fWasInteractive = self.__fMatplotlib.is_interactive()
    self.__fMatplotlib.interactive(True)
    self.__fPendingCleanup = self.__GtkCleanup
    
  def __GtkCleanup(self):
    if kDebug:
      print ("__GtkCleanup")
    self.__fPendingCleanup = None
    self.__fGTK.mainloop = self.__fSavedGTKMainloop
    self.__fGTK.main = self.__fSavedGTKMain
    self.__fMatplotlib.interactive(self.__fWasInteractive)
    
  def __GtkUpdate(self):
    if kDebug:
      print("__GtkUpdate")
    import time
    start_time = time.time()
    while self.__fGTK.events_pending() and time.time() < start_time + 0.1:
      self.__fGTK.main_iteration()
    
  def __WxPrepare(self):
    if kDebug:
      print ("__WxPrepare")
    self.__fWXCore.PyApp_MainLoop = self.__Noop
    self.__fPendingCleanup = self.__WxCleanup
    
  def __WxCleanup(self):
    if kDebug:
      print ("__WxCleanup")
    self.__fPendingCleanup = None
    if self.__fMatplotlib.is_interactive() and not self.__fInitialShow and 'pylab' in sys.modules:
      sys.modules['pylab'].show()
      self.__fInitialShow = 1
    
  def __WxUpdate(self):
    if kDebug:
      print("__WxUpdate")
      
    app = self.__fWX.GetApp()
    if app is not None:
      import time
      start_time = time.time()
      self.__fWXEventLoopActivator = self.__fWX.EventLoopActivator(self.__fWxEventloop)
      try:
        while self.__fWxEventloop.Pending() and time.time() < start_time + 0.1:
          try:
            self.__fWxEventloop.Dispatch()
          except:
            if kDebug:
              print("dispatch failed")
            break
          app.ProcessIdle()
      finally:
        self.__fWXEventLoopActivator = None
    elif kDebug:
      print("app is none")
    
  def __MacOSXPrepare(self):
    if kDebug:
      print ("__MacOSXPrepare")
    self.__fMacOSX_Show.mainloop = self.__Noop
    self.__fPendingCleanup = self.__MacOSXCleanup
    self.__fPyPlotImShowCalled = False
    self.__fOrigPyPlotImShow = None

    # Make sure plots shown with pyplot.imshow() are also shown.  This works
    # fine on other OSes but not Mac without a call to show().  Note that
    # this won't work if user does 'from matplotlib.pyplot import *' or
    # similar, but that doesn't seem to be the predominant style of use
    # and fixing it would require watching for pyplot import.
    mp = sys.modules.get('matplotlib')
    if hasattr(mp, 'pyplot'):
      self.__fOrigPyPlotImShow = mp.pyplot.imshow
      def wrap_imshow(*args, **kw):
        self.__fPyPlotImShowCalled = True
        self.__fOrigPyPlotImShow(*args, **kw)
      mp.pyplot.imshow = wrap_imshow
    
  def __MacOSXCleanup(self):
    if kDebug:
      print("__MacOSXCleanup")
    self.__fPendingCleanup = None

    # Make pyplot.imshow() work
    mp = sys.modules.get('matplotlib')
    if hasattr(mp, 'pyplot'):
      if self.__fPyPlotImShowCalled:
        mp.pyplot.show()
        self.__fPyPlotImShowCalled = False
      if self.__fOrigPyPlotImShow is not None:
        mp.pyplot.imshow = self.__fOrigPyPlotImShow
        self.__fOrigPyPlotImShow = None
      
    self.__fMacOSX_Show.mainloop = self.__fMacOSX_Mainloop
    
  def __MacOSXUpdate(self):
    if kDebug:
      print("__MacOSXUpdate")
      
    try:
      for i in self.__fMatplotlib.pyplot.get_fignums():
        try:
          fig = self.__fMatplotlib.pyplot.figure(i)
          fig.canvas.draw()
          fig.canvas.start_event_loop(.01)
        except:
          if kDebug:
            print("exception trying to start_event_loop")
          continue
    except:
      if kDebug:
        print("exception iterating over figures")
    
  def __Noop(self, *args, **kw):
    pass
    
