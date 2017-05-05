#########################################################################
""" Test runner utilities

Copyright (c) 1999-2012, Archaeopteryx Software, Inc.

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

import os.path
import sys
import time
import unittest
try:
    import threading
except ImportError:
    threading = None

import traceback

if sys.version_info < (3, 0):
    _unicode = unicode
    io = None
else:
    _unicode = str
    import io
    
def xml_escape(text):
    """ Escape the text so it doesn't include any xml control characters
    and sanitize it so it's a sane unicode string, replacing characters
    if needed.  Return type is always str so it's an unicode instance 
    in Python 3 and a utf8 encoded byte string in Python 2 """
    
    if isinstance(text, _unicode):
        utext = text
    else:
        utext = _unicode(text, 'utf_8', 'replace')

    utext = utext.replace('&', '&amp;')
    utext = utext.replace('<', '&lt;')
    utext = utext.replace('>', '&gt;')
    utext = utext.replace('"', '&quot;')

    if isinstance(utext, str):
        return utext
    else:
        return utext.encode('utf_8')

def escaped_split(text):
    """Split the text on ' ' ignoring any '\ '."""
    
    parts = text.split()
    split_parts = []
    part_prefix = []
    for i, part in enumerate(parts):
        if part.endswith('\\'):
            part_prefix.append(part)
        elif part_prefix:
            split_parts.append(' '.join(part_prefix) + ' ' + part)
            part_prefix = []
        else:
            split_parts.append(part)
    return split_parts
        
    
class XmlStream(object):
    
    _top_tag = 'test-results'

    # Set encoding to 'UTF-8', regardless of platform and sys.stdout.encoding
    encoding = 'UTF-8'
    
    def __init__(self, raw_stream, write_top_tag=1):
        if threading is not None:
            self._writing_lock = threading.RLock()
        else:
            self._writing_lock
        self._raw_stream = raw_stream
        self._pending_output = None

        self._write_top_tag = write_top_tag
        if self._write_top_tag:
            self.write_raw('<%s>' % self._top_tag)
        
    def __getattr__(self, name):
        return getattr(self._raw_stream, name)
    
    def _acquire_writing_lock(self):
        
        if self._writing_lock is not None:
            self._writing_lock.acquire()
            
    def _release_writing_lock(self):
        
        if self._writing_lock is not None:
            self._writing_lock.release()

    def finish(self):
        
        if self._write_top_tag:
            self.write_raw('</%s>' % self._top_tag)

        self._flush_output()
        self._raw_stream = None
    
    def write(self, s):
        
        self._acquire_writing_lock()
        try:
            if self._pending_output is None:
                self._pending_output = []
            self._pending_output.append(s)
            if '\n' in s:
                self._flush_output()
        finally:
            self._release_writing_lock()
            
    def writeln(self, ln):
        self.write(ln + '\n')
        
    def write_raw(self, s):
        """ Write s to the raw stream; it can either be a unicode or bytes
        instance. """

        # Py3 io.TextIOWrapper needs unicode instances; everything else
        # needs utf8 encoded bytes

        if (sys.version_info >= (3, 0) and io is not None
            and isinstance(self._raw_stream, io.TextIOWrapper)):
            if not isinstance(s, str):
                s = str(s, 'utf_8', 'replace')
            self._raw_stream.write(s)
        else:
            if isinstance(s, _unicode):
                s = s.encode('utf_8')
            self._raw_stream.write(s)
        
    def write_tag(self, name, content, **kw):
        
        self._acquire_writing_lock()
        try:
            if kw:
                attrib_list = []
                for key, value in kw.items():
                    attrib_list.append('%s="%s"' % (key, xml_escape(str(value))))
                self.write_raw('<%s %s>' % (name, ' '.join(attrib_list)))
            else:
                self.write_raw('<%s>' % name)
            if content:
                self.write_raw(xml_escape(content))
            self.write_raw('</%s>' % name)
        finally:
            self._release_writing_lock()
            
    def _start_test(self, name, filename, lineno=None, code_filename=None):

        self._acquire_writing_lock()
        try:
            self._flush_output()
            self.write_raw('<test name="%s" filename="%s"' 
                           % (xml_escape(name), xml_escape(filename)))
            if lineno is not None:
                self.write_raw(' lineno="%s"' % str(lineno))
            if code_filename is not None:
                self.write_raw(' code_filename="%s"' % xml_escape(code_filename))
                               
            self.write_raw('>\n')
        finally:
            self._release_writing_lock()

    def _finish_test(self, result=None):
        
        self._acquire_writing_lock()
        try:
            self._flush_output()
            if result is not None:
                self.write_tag('result', result)
            self.write_raw('</test>\n')

        finally:
            self._release_writing_lock()

    def _flush_output(self, enclose_in_tag=1):

        self._acquire_writing_lock()
        try:
            if self._pending_output is None:
                return
            
            output = ''.join(self._pending_output)
            self._pending_output = None
            
            if enclose_in_tag:
                self.write_tag('output', output)
                self.write_raw('\n')
            else:
                self.write_raw(output)
                
            if __debug__:
                self.flush()
                
        finally:
            self._release_writing_lock()
        
    def _write_exc_info(self, err):
        try:
            exc_type, value, tb = err
        except:
            self.write_tag('exception', 'internal failure')
            return

        if isinstance(value, SyntaxError):
            syntax_attrib = 'yes'
        else:
            syntax_attrib = 'no'

        self._acquire_writing_lock()
        try:
            self.write_raw('<exception syntax="%s">\n' % syntax_attrib)
            self.write_tag('type', repr(exc_type))
            
            formatted_value = traceback.format_exception_only(exc_type, value)
                
            self.write_tag('repr', formatted_value[-1])
                
            if isinstance(value, SyntaxError):
                try:
                    msg, (filename, lineno, offset, badline) = value
                except Exception:
                    pass
                else:
                    self.write_tag('syntaxinfo', badline, 
                                          lineno=lineno,
                                          offset=offset,
                                          filename=filename)
    
            self.__WriteTraceback(tb)
                
            self.write_raw('</exception>\n')
        finally:
            self._release_writing_lock()

    def __WriteTraceback(self, tb):
        
        self._acquire_writing_lock()
        try:
            self.write_raw('<traceback>\n')
            while tb is not None:
                self.__WriteFrame(tb.tb_frame, tb.tb_lineno)
                tb = tb.tb_next
            self.write_raw('</traceback>\n')
            
        finally:
            self._release_writing_lock()

    def __GetFilename(self, frame):
        
        globals_filename = frame.f_globals.get('__file__')
        if globals_filename is not None:
            globals_filename = os.path.abspath(globals_filename)
            if globals_filename[-4:] in ['.pyc', '.pyo']:
                globals_filename = globals_filename[:-4] + '.py'
            if os.path.isfile(globals_filename):
                return globals_filename
        
        co_filename = os.path.abspath(frame.f_code.co_filename)
        return co_filename
        
    def __GetSourceLine(self, frame, filename, lineno):
        
        try:
            import linecache
        except Exception:
            return None
        
        try:
            # Newer versions take a filename arg, but earlier ones did not
            linecache.checkcache(filename)
        except TypeError:
            linecache.checkcache()
            
        try:
            # 2.5 takes module globals, but earlier versions did not
            try:
                line = linecache.getline(filename, lineno, frame.f_globals)
            except TypeError:
                line = linecache.getline(filename, lineno)
        except Exception:
            return None
        line = line.rstrip()
        return line

    def __WriteFrame(self, frame, lineno):
        
        try:
            lineno_str = str(int(lineno))
        except:
            lineno_str = '?'
            lineno = None
        
        filename = self.__GetFilename(frame)
        
        self._acquire_writing_lock()
        try:
            self.write_raw('<frame lineno="%s" filename="%s" name="%s">' 
                           % (lineno_str, xml_escape(filename),
                              xml_escape(frame.f_code.co_name)))
            if lineno is not None:
                line = self.__GetSourceLine(frame, filename, lineno)
                if line is not None:
                    self.write_raw(xml_escape(line))
                    
            self.write_raw('</frame>\n')

        finally:
            self._release_writing_lock()

class NonXmlStream(XmlStream):
    
    def __init__(self, raw_stream):
        XmlStream.__init__(self, raw_stream, 0)
            
    def write_tag(self, name, content, **kw):
        pass
        
    def _start_test(self, name, filename, lineno=None, code_filename=None):
        self._flush_output()
 
    def _finish_test(self, result=None):
        self._flush_output()

    def _flush_output(self, enclose_in_tag=0):
        XmlStream._flush_output(self, enclose_in_tag)
        
    def _write_exc_info(self, err):
        try:
            exc_type, value, tb = err
        except:
            self.write_raw('Internal failure while printing exception')
            return
        sys.excepthook(exc_type, value, tb)

try:
    _TestResultBase = unittest._TextTestResult
except AttributeError:
    _TestResultBase = unittest.TestResult
def _InitTestResultBase(inst, stream):
    if _TestResultBase == unittest.TestResult:
        return _TestResultBase.__init__(inst)
    else:
        return _TestResultBase.__init__(inst, stream, 0, 0)
    
SUCCEEDED = 'succeeded'        
ERROR = 'error'
FAILED = 'failed'
SKIPPED = 'skipped'

class XmlTestResult(_TestResultBase):
    """A test result class that can print XML formatted text results to a stream."""

    def __init__(self, stream):
        _InitTestResultBase(self, stream)
        self.stream = stream

    def _getCodeLocation(self, call, use_module_name=True):
        """ Get filename, lineno function or method is 'defined in'.  If use_method_name
        is true, use the __module__ attribute and the find filename from there.
        Note that if callable is the result of a decorator, the filename of a 
        wrapper function may be returned, unless use_module_name is true and
        functools.wraps or the equivalent is used to update the wrapper's
        function attributes. """
        
                
        try:
            if isinstance(call, type(self._getCodeLocation)):
                if sys.version_info < (3, 0):
                    func = call.im_func
                else:
                    func = call.__func__
            else:
                func = call
                
            if sys.version_info < (3, 0):
                func_code = func.func_code
            else:
                func_code = func.__code__
        
            filename = None
            if use_module_name:
                try:
                    module_name = call.__module__
                except AttributeError:
                    module_name = None
                mod = sys.modules.get(module_name)
                if mod is not None:
                    try:
                        filename = self._normalizeFilename(mod.__file__)
                    except AttributeError:
                        pass      

            if filename is None:
                if sys.version_info < (3, 0):
                    func_globals = func.func_globals
                else:
                    func_globals = func.__globals__
                    
                try:
                    filename = self._normalizeFilename(func_globals['__file__'])
                except KeyError:
                    filename = self._normalizeFilename(func_code.co_filename)
                    
            try:
                lineno = func_code.co_firstlineno
            except AttributeError:
                lineno = 0
            return filename, lineno
        except Exception:
            return '??', 0

    def _testClassFilename(self, test):
        """ Get the filename where a test class is defined. """
        
        try:
            mod = sys.modules[test.__class__.__module__]
        except (AttributeError, KeyError):
            pass
        else:
            try:
                return self._normalizeFilename(mod.__dict__['__file__'])
            except KeyError:
                return self._normalizeFilename(mod.__file__)
        
        filename, lineno = self._sourceCodeLocation(test)
        return filename

    def _sourceCodeLocation(self, test):
        """ Get the filename and the lineno where the source code for a test is. """

        try:
            meth = getattr(test, test._testMethodName)
        except AttributeError:
            pass
        else:
            return self._getCodeLocation(meth)
        
        return self._getCodeLocation(test)
    
    def _normalizeFilename(self, filename):
        """ Normalize: get abs path and convert .pyc or .pyo to .py """

        if filename is None or filename == '??' or filename.startswith('<'):
            return filename

        filename = os.path.abspath(filename)
        if (filename.lower().endswith('.pyc') or filename.lower().endswith('.pyo')) \
           and os.path.exists(filename[:-1]):
            filename = filename[:-1]
            
        return filename
        
    def _testDottedName(self, test):
        """ Return name of test as simple dotted name,
        e.g. ClassName.methodName """

        try:
            name = repr(test)
        except Exception:
            return '??'
        
        if name.startswith('<') and name.endswith('>'):
            name = name[1:-1]
        try:
            module_name = test.__module__
        except AttributeError:
            pass
        else:
            if name.startswith(module_name + '.'):
                name = name[len(module_name + '.'):]
        name = name.replace(' testMethod=', '.')
        return name
    
    def startTest(self, test):
        unittest.TestResult.startTest(self, test)
        class_filename = self._testClassFilename(test)
        code_filename, lineno = self._sourceCodeLocation(test)
        name = self._testDottedName(test)
        self.stream._start_test(name, class_filename, code_filename=code_filename,
                                lineno=lineno)

    def stopTest(self, test):
        self.stream._finish_test()
        
    def addSuccess(self, test):
        unittest.TestResult.addSuccess(self, test)
        self.stream.write_tag('result', SUCCEEDED)

    def addError(self, test, err):
        unittest.TestResult.addError(self, test, err)
        self.stream._write_exc_info(err)
        self.stream.write_tag('result', ERROR)

    def addFailure(self, test, err):
        unittest.TestResult.addFailure(self, test, err)
        self.stream._write_exc_info(err)
        self.stream.write_tag('result', FAILED)
        
    try:
        unittest.TestResult.addSkip
    except AttributeError:
        pass
    else:
        def addSkip(self, test, reason):
            unittest.TestResult.addSkip(self, test, reason)
            self.stream.write_tag('result', SKIPPED)

    try:
        unittest.TestResult.addUnexpectedSuccess
    except AttributeError:
        pass
    else:
        def addUnexpectedSuccess(self, test):
            unittest.TestResult.addUnexpectedSuccess(self, test)
            self.stream.write_tag('result', FAILED)

    try:
        unittest.TestResult.addExpectedFailure
    except AttributeError:
        pass
    else:
        def addExpectedFailure(self, test, err):
            unittest.TestResult.addExpectedFailure(self, test, err)
            self.stream._write_exc_info(err)
            self.stream.write_tag('result', SUCCEEDED)


        
class XmlTestRunner:
    """A test runner class that returns results in XML form.

    It prints out the names of tests as they are run, errors as they
    occur, and a summary of the results at the end of the test run.
    """

    def __init__(self, result):
        self.result = result
    def _makeResult(self):
        return self.result
    def run(self, test):
        "Run the given test case or test suite."
        
        startTime = time.time()
        test(self.result)
        stopTime = time.time()
        timeTaken = stopTime - startTime
        return self.result

def samefile(name1, name2):
    if sys.platform != 'win32':
        return os.path.samefile(name1, name2)
    
    name1 = os.path.normcase(os.path.normpath(os.path.abspath(name1)))
    name2 = os.path.normcase(os.path.normpath(os.path.abspath(name2)))
    return name1 == name2

def process_directory_arg(argv):
    # Set sys.path[0] directory so tests run as if test file was executed
    # Use --directory= value in sys.argv[0] or cwd; Note this is limited to
    # names representable in file system encoding
         
    module_dir = GetModuleDir(argv)
    if module_dir is not None and os.path.isdir(module_dir):
        dirname = os.path.dirname(os.path.abspath(sys.argv[0]))
        if samefile(dirname, sys.path[0]):
            sys.path[0] = module_dir
        else:
            sys.path.insert(0, module_dir)
            
    return module_dir
 
def GetModuleDir(argv):
    """ Returns default module directory.  Pops first --directory arg from
    argv if there is one. """
    
    dir_arg_prefix = '--directory='
    dir_arg = PopFromArgv(argv, dir_arg_prefix)
    if dir_arg is not None:
        return dir_arg[len(dir_arg_prefix):]
    else:
        return os.getcwd()

def PopFromArgv(argv, prefix, default=None):
    """ Return the first arg that starts with prefix and then remove in from 
    argv.  Default is returned if no such argument is found. """
    
    for i, arg in enumerate(argv):
        if arg.startswith(prefix):
            del argv[i]
            return arg
        
    return default
            
def CreateOutputStream(argv, xml_stream_cls=XmlStream, 
                       nonxml_stream_cls=NonXmlStream):
    """ Create stream to write results to """

    append_arg = PopFromArgv(argv, '--append-to-file')
    
    raw_stream = sys.stdout
    filename = PopFromArgv(argv, '--output-file=')
    if filename is not None:
        filename = filename[len('--output-file='):]
        if append_arg is not None:
            mode = 'a'
        else:
            mode = 'w'
        if sys.version_info < (3, 0):
            mode = mode + 'b'
        raw_stream = open(filename, mode)
        
    fd_str = PopFromArgv(argv, '--output-fd=')
    if fd_str is not None:
        fd_str = fd_str[len('--output-fd='):]
        if fd_str.isdigit():
            try:
                fd = int(fd_str)
            except:
                fd = None
            if fd is not None:
                raw_stream = os.fdopen(fd, 'wb')
    
    osfhandle_str = PopFromArgv(argv, '--output-osfhandle=')
    if osfhandle_str is not None:
        osfhandle_str = osfhandle_str[len('--output-osfhandle='):]
        if osfhandle_str.isdigit() or (osfhandle_str[:1] == '-'
                                       and osfhandle_str[1:].isdigit()):
            try:
                osfhandle = int(osfhandle_str)
            except:
                osfhandle = None
            if osfhandle is not None:
                import msvcrt
                fd = msvcrt.open_osfhandle(osfhandle, os.O_BINARY)
                raw_stream = os.fdopen(fd, 'wb')

    no_xml = PopFromArgv(argv, '--no-xml')
    if no_xml is None:
        xmlout = xml_stream_cls(raw_stream)
    else:
        xmlout = nonxml_stream_cls(raw_stream)
    return xmlout


def SetupSysArgv(argv, get_only=False):
    """Sets up sys.argv specified for the tests themselves"""

    sysargv = PopFromArgv(argv, '--runargs=')
    if sysargv is None:
        return []
    
    sysargv = sysargv[len('--runargs="'):-1]
    sysargv = escaped_split(sysargv)

    if not get_only:
        sys.argv = sysargv
        
    return sysargv
