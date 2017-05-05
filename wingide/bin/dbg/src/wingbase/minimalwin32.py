#########################################################################
""" minimalwin32.py -- Exposes subset of win32 api needed to find patch dirs

Minimal wrapping is done except to raise exceptions when win32 errors
occur or to return strings that are returned via caller allocated buffers
in simple cases.  All strings are expected to be unicode and *W api's 
are used.

Copyright (c) 1999-2012, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
#########################################################################

import functools
import sys
if sys.platform != 'win32':
    raise ImportError('win32 module is only usable on win32')

from ctypes import *
from ctypes.wintypes import *
_user32 = WinDLL("user32")
_kernel32 = WinDLL("kernel32")
_mpr = WinDLL("mpr")
_winsock2 = WinDLL("ws2_32")
_gdi32 = WinDLL("gdi32")
_shell32 = WinDLL('shell32')

ERROR_SUCCESS = 0
NO_ERROR = 0

ERROR_BAD_DEVICE = 1200
ERROR_CONNECTION_UNAVAIL = 1201
ERROR_EXTENDED_ERROR = 1208
ERROR_MORE_DATA = 234
ERROR_NOT_SUPPORTED = 50
ERROR_NO_NET_OR_BAD_PATH = 1203
ERROR_NO_NETWORK = 1222
ERROR_NOT_CONNECTED = 2250
ERROR_ENVVAR_NOT_FOUND = 203
ERROR_INCORRECT_FUNCTION = 1
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
ERROR_INVALID_HANDLE = 6
ERROR_ACCESS_DENIED = 5 # Variable c_long
ERROR_NETNAME_DELETED = 64
ERROR_NETWORK_ACCESS_DENIED = 65
ERROR_INVALID_PARAMETER = 87
ERROR_OPERATION_ABORTED = 995 # Variable c_long
ERROR_IO_INCOMPLETE = 996 # Variable c_long
ERROR_IO_PENDING = 997
ERROR_TOO_MANY_CMDS = 56
ERROR_UNEXP_NET_ERR = 59
ERROR_INVALID_USER_BUFFER = 1784
ERROR_HANDLE_EOF = 38
ERROR_BROKEN_PIPE = 109

def _check_return_value(func, invalid_return, no_error_ok=False):
    """ Creates new callable that calls func and raises WinError if the
    return value is invalid_return.  If no_error_ok is true, no exception
    will be raised if GetLastError() returns NO_ERROR (0) """
    
    @functools.wraps(func)
    def wrapper(*args, **kw):
        retval = func(*args, **kw)
        if retval == invalid_return:
            exc = WinError()
            if not (no_error_ok and exc.winerror == NO_ERROR):
                raise exc
        return retval
        
    return wrapper

def to_unicode(s):
    if s is None:
        return None
    if sys.version_info < (3, 0) and not isinstance(s, unicode):
        try:
            s = unicode(s, 'utf-8')
        except:
            print('Bad utf8 byte string passed to win32 api: ' + repr(s))
            s = unicode(s, 'utf-8', 'replace')
            
    return s


SetLastError = _kernel32.SetLastError
SetLastError.argtypes = [DWORD]

GetEnvironmentVariableW = _kernel32.GetEnvironmentVariableW
GetEnvironmentVariableW.restype = DWORD
GetEnvironmentVariableW.argtypes = [LPWSTR, LPWSTR, DWORD]

def GetEnvironmentVariable(name, default=None):
    """ Gets value as unicode.  The default is returned if the variable 
    is not set """
    
    name = to_unicode(name)
    wchar_buffer = create_unicode_buffer('\0', size=MAX_PATH)
    count = GetEnvironmentVariableW(name, wchar_buffer, MAX_PATH)

    if count >= MAX_PATH:
        wchar_buffer = create_unicode_buffer('\0', size=count+1)
        count = GetEnvironmentVariableW(name, wchar_buffer, count+1)

    if count == 0:
        # Note that the return value of a variable set to an empty string will be 0 so
        # check if the variable exists but is set to an empty string after getting 
        # potential exception.  Always call GetEnvironmentVariableW again because
        # the win error isn't reset to 0 when 0 is returned for an empty string
        # value
        exc = WinError()

        # GetEnvironmentVariable doesn't reset the last error on success.  It also
        # seems to sometimes considers not finding the variable to be a success;
        # yes this is an old and idiosyncratic api function
        SetLastError(ERROR_SUCCESS)
        count_with_null = GetEnvironmentVariableW(name, wchar_buffer, 0)
        last_error = GetLastError()
        if count_with_null == 0 and last_error in (ERROR_SUCCESS, ERROR_ENVVAR_NOT_FOUND):
            return default
        
        if count_with_null == 1:
            return to_unicode('')

        raise exc
    
    return unicode(wchar_buffer[:count])

SetEnvironmentVariableW = _kernel32.SetEnvironmentVariableW
SetEnvironmentVariableW.restype = BOOL
SetEnvironmentVariableW.argtypes = [LPWSTR, LPWSTR]

SetEnvironmentVariable = _check_return_value(SetEnvironmentVariableW, 0)

# Note that wstrings contain embedded \0's so use void pointers to avoid auto conversions
GetEnvironmentStringsW = _kernel32.GetEnvironmentStringsW
GetEnvironmentStringsW.restype = c_void_p
GetEnvironmentStringsW.argtypes = []
FreeEnvironmentStringsW = _kernel32.FreeEnvironmentStringsW
FreeEnvironmentStringsW.restype = BOOL
FreeEnvironmentStringsW.argtypes = [c_void_p]

def GetEnvironmentStrings():
    
    # Memory block returned is terminated by two \0 wchars
    
    # Byte width of a wchar should be determined by ctypes but it's always
    # going to be 2 on win32
    
    bytes_per_wchar = 2
    
    start_ptr = GetEnvironmentStringsW()
    if start_ptr is None:
        raise WinError()
    
    end_ptr = start_ptr
    while wstring_at(end_ptr, 2) != '\0\0':
        end_ptr += bytes_per_wchar

    size = end_ptr - start_ptr

    retval = wstring_at(start_ptr, size / bytes_per_wchar)

    FreeEnvironmentStringsW(start_ptr)
    return retval

SHGetFolderPathW = _shell32.SHGetFolderPathW
SHGetFolderPathW.restype = HRESULT
SHGetFolderPathW.argtypes = [HWND, c_int, HANDLE, DWORD, LPWSTR]

CSIDL_APPDATA = 0x1A
CSIDL_LOCAL_APPDATA = 0x1C
CSIDL_FLAG_CREATE = 0x8000

SHGFP_TYPE_CURRENT = 0
SHGFP_TYPE_DEFAULT = 1

S_OK = 0

def SHGetFolderPath(nFolder, create):
    
    # XXX Should transition to using SHGetKnownFolderPath
    
    if create:
        nFolder |= CSIDL_FLAG_CREATE
    
    wbuffer = create_unicode_buffer('\0', MAX_PATH + 1)
    hresult = SHGetFolderPathW(None, nFolder, None, SHGFP_TYPE_CURRENT, wbuffer)
    if hresult != S_OK:
        # hresults have their own error codes and don't necessarily set the last error
        raise OSError('SHGetFolderPath failed: hresult = ' + str(hresult))
    
    return wbuffer.value
