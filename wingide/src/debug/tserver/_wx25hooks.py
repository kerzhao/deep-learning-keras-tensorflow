#########################################################################
""" _wx25hooks.py -- wxPython 2.5 socket management hooks for the Wing debugger

Copyright (c) 1999-2012, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

"""
#########################################################################

import types
import sys

from . import _wxhooks

# The name of the module to watch for that indicates presence of this
# supported mainloop environment
kIndicatorModuleName = 'wx'

# The hook is activated periodically -- timeout (in milliseconds) to poll
kPollTimeout = 500

#########################################################################
# wxPython-specific support for managing the debug server sockets,
# using the new Timer class name
#########################################################################
class _SocketHook(_wxhooks._SocketHook):
  _kTimerClassName = 'Timer'
  _kAppClassName = 'App'
  _kGetAppFunctionName = 'GetApp'
  _kIndicatorModuleName = kIndicatorModuleName

  #-----------------------------------------------------------------------
  def _ValidClass(self, c):
    if sys.hexversion >= 0x03000000:
      return type(c) is type
    else:
      return isinstance(c, types.TypeType)
        
