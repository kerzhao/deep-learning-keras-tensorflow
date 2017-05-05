#########################################################################
""" Test runner for pytest

Copyright (c) 1999-2015, Archaeopteryx Software, Inc.

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

import sys
import imp
import os.path

def LoadCommon():
    """ Load the common module w/ imp so it works even w/o being in path. """
    
    our_dir = os.path.dirname(__file__)
    f, filename, info = imp.find_module('wingtest_common', [our_dir])
    try:
        return imp.load_module('wingtest_common', f, filename, info)
    finally:
        f.close()
    
wingtest_common = LoadCommon()
if 0:
    import wingtest_common
    
#-----------------------------------------------------------------------
def QuotedSplit(txt, sep=' ', allow_esc=True):
    """Like string.split(txt, sep) but the resulting list contains items
    so that any quoted groups are preserved as a single item and leading
    and trailing white space is removed from each item.  Set allow_esc
    to True to allow \" and \' to escape processing of the following quote."""

    in_quote = None
    cur_part = []
    retval = []
    seen_esc = False
    for c in txt:

        # Currently processing a quoted group
        if in_quote:
            if not seen_esc and c == in_quote:
                cur_part.append(c)
                in_quote = None
            else:
                cur_part.append(c)

        # Outside of a quoted group
        else:
            if not seen_esc and c == sep:
                retval.append(''.join(cur_part).strip())
                cur_part = []
            elif not seen_esc and c in '"\'':
                cur_part.append(c)
                in_quote = c
            else:
                cur_part.append(c)

        if allow_esc and c == '\\':
            if seen_esc:
                seen_esc = False
            else:
                seen_esc = True
        else:
            seen_esc = False

    # Add any left over part to the result (in case of missing trailing quote)
    if cur_part is not None:
        retval.append(''.join(cur_part).strip())

    return retval

    
class CPytestPlugin:
    
    def __init__(self, result, runner):
        self.result = result
        self.stream = result.stream
        self.runner = runner
        
        self._session = None
        
    def pytest_sessionstart(self, session):
        self._session = session
        
    def pytest_internalerror(self, excrepr, excinfo):
        print("INTERNAL ERROR:", str(excinfo))
        
    #def pytest_collectstart(self, collector):
        #print(collector)
        
    #def pytest_itemcollected(self, item):
        #print(item)

    #def pytest_collectreport(self, report):
        #print(report)
        
    #def pytest_deselected(self, items):
        #print(items)
        
    def pytest_runtest_logreport(self, report):
        rel_filename, lineno, test = report.location
        abs_filename_path = self._session.fspath.join(rel_filename)
        code_filename = str(abs_filename_path)

        if report.when == 'setup':
            self.stream._start_test(test, code_filename, lineno=lineno)
            
        elif report.when == 'call':
            if report.failed:
                self.__write_exc_info(report.longrepr)
                self.stream.write_tag('result', wingtest_common.FAILED)
            elif report.skipped:
                self.stream.write_tag('result', wingtest_common.SKIPPED)
            elif report.passed:
                self.stream.write_tag('result', wingtest_common.SUCCEEDED)
            else:
                #self.stream._write_exc_info(err)
                self.stream.write_tag('result', wingtest_common.ERROR)
            
        elif report.when == 'teardown':
            self.result.stream._finish_test()
            
    def pytest_exception_interact(self, node, call, report):
        if call.when == 'memocollect':
            self.__write_syntax_exc_info(call.excinfo)
        if 'WINGDB_ACTIVE' not in os.environ:
            return

        # Need to explicitely report the exception to the debugger because of
        # how pytest is designed
        exc, v, tb = call.excinfo._excinfo
        frames_wanted = len(call.excinfo.traceback)
        frames = []
        i = 0
        while tb:
            frames.append(tb)
            tb = tb.tb_next
        tb = frames[-frames_wanted]
        filename = tb.tb_frame.f_code.co_filename
        
        try:
            debugger = sys._wing_debugger.GetServer()
        except:
            debugger = None
        if debugger is not None:
            debugger._CB_Exception(tb.tb_frame, (exc, v, tb))

    def __write_syntax_exc_info(self, excinfo):
        
        exc = excinfo.exconly()
        parts = exc.splitlines()
        filtered = []
        for part in parts:
            if part.startswith('E '):
                filtered.append(part[1:].strip())

        if len(filtered) == 4 and 'SyntaxError' in filtered[-1]:
            syntax_attrib = 'yes'
            fn, lineno, co_name = self.__parse_tb_file_lineno(filtered[0])
            offset = 0
            exc_repr = filtered[-1]
            exc_type = 'SyntaxError'
        else:
            syntax_attrib = 'no'
            exc_repr = exc
            exc_type = repr(excinfo)
            
        self.stream._acquire_writing_lock()
        try:
            self.stream.write_raw('<exception syntax="%s">\n' % syntax_attrib)
            self.stream.write_tag('type', exc_type)
            
            self.stream.write_tag('repr', exc_repr)
            
            if syntax_attrib == 'yes':
                self.stream.write_tag('syntaxinfo', lineno, 
                                      lineno=lineno,
                                      offset=0,
                                      filename=fn)
    
            #self.__write_traceback(tb)
                
            self.stream.write_raw('</exception>\n')
        finally:
            self.stream._release_writing_lock()

    def __parse_tb_file_lineno(self, line):
        # Unfortunately we need to parse out the needed info -- note that we
        # avoid looking for 'File', 'line', and 'in' so it can work in
        # non-English locales
        
        parts = QuotedSplit(line, sep=',')
        
        fn = QuotedSplit(parts[0])[-1]
        if fn[0] == fn[-1] and fn[0] in '\'"':
            fn = fn[1:-1]
            
        lineno = parts[1].split()[-1]
            
        if len(parts) == 3:
            co_name = parts[2].split()[-1]
        else:
            co_name = '<module>'
            
        return fn, lineno, co_name
            
    def __write_exc_info(self, longrepr):

        # Unfortunately there isn't access to the actual exception
        try:
            tb_lines = longrepr.reprtraceback.reprentries[0].lines
        except AttributeError:
            tb_lines = longrepr.splitlines()
        exc_repr, exc_type, tb = self.__parse_tb_lines(tb_lines)
        
        self.stream._acquire_writing_lock()
        try:
            self.stream.write_raw('<exception syntax="no">\n')
            self.stream.write_tag('type', exc_type)
            
            self.stream.write_tag('repr', exc_repr)
    
            self.__write_traceback(tb)
                
            self.stream.write_raw('</exception>\n')
        finally:
            self.stream._release_writing_lock()

    def __parse_tb_lines(self, tb_lines):
        
        # Unfortunately there isn't access to the actual traceback
        if len(tb_lines) == 3 and isinstance(tb_lines[1], list):
            pfx, lines, exc_repr = tb_lines
            ret_lines = lines.strip().splitlines()
            exc_repr = exc_repr.strip()

        # This case occurs with syntax errors within imported modules
        else:
            # Normalize lines -- the formatting is not uniform
            norm_lines = []
            for tbl in tb_lines:
                sublines = tbl.splitlines()
                norm_lines.extend(sublines)
                
            ret_lines = [l.rstrip() for l in norm_lines]
            if ret_lines and ret_lines[0].strip().startswith('Traceback'):
                ret_lines = ret_lines[1:]
            exc_repr = norm_lines[-1].strip()
        
        parts = exc_repr.split(':')
        if len(parts) > 1:
            exc_type = parts[0]
        else:
            exc_type = exc_repr
            
        return exc_repr, exc_type, ret_lines
        
    def __write_traceback(self, tb):
        
        self.stream.write_raw('<traceback>\n')
        for i in range(0, len(tb), 2):
            if i + 1 > len(tb) - 1 or ('File' not in tb[i] and '"' not in tb[i] and 'line' not in tb[i]):
                break
            filename, lineno, co_name = self.__parse_tb_file_lineno(tb[i])
            codeline = tb[i+1]
            self.__write_frame(filename, lineno, co_name, codeline)
        self.stream.write_raw('</traceback>\n')
        
    def __write_frame(self, filename, lineno, co_name, codeline):

        try:
            lineno_str = str(int(lineno))
        except:
            lineno_str = '?'
        
        self.stream.write_raw(
            '<frame lineno="%s" filename="%s" name="%s">' % 
            (lineno_str, wingtest_common.xml_escape(filename),
             wingtest_common.xml_escape(co_name))
        )
        self.stream.write_raw(wingtest_common.xml_escape(codeline))
                
        self.stream.write_raw('</frame>\n')
        
def main(argv):

    module_dir = wingtest_common.GetModuleDir(argv)
    
    sysargv = wingtest_common.SetupSysArgv(argv)
    xmlout = wingtest_common.CreateOutputStream(argv)
    sys.stdout = sys.stderr = xmlout

    module_pos = argv.index('-q')
    module_names = argv[module_pos+1:]
    
    try:
        RunInSingleDir(module_names, xmlout, module_dir, sysargv)
    finally:
        xmlout.finish()

def RewriteTestSpec(dirname, test_spec):
    """ Rewrite module test spec in form pytest wants -- an absolute pathname
    plus any in-module specs seperated by :: """
    
    parts = test_spec.split('.')

    # Pop off the filename parts; note that specifying a package name
    # does not work as of pytest 2.7.2 but package names are not used
    # by Wing
    module_fullpath = os.path.join(dirname, parts.pop(0))
    while os.path.isdir(module_fullpath) and len(parts) != 0:
        module_fullpath = os.path.join(module_fullpath, parts.pop(0))
    
    if not module_fullpath.endswith('.py'):
        module_fullpath += '.py'

    if len(parts) == 0:
        return module_fullpath

    return module_fullpath + '::' + '::'.join(parts)
        
def RunInSingleDir(module_name_seq, xmlout, dirname, sysargv):
    """ Run pytest TestProgram w/ given argv"""

    module_fullpath_list = [RewriteTestSpec(dirname, spec) for spec 
                            in module_name_seq]
        
    result = wingtest_common.XmlTestResult(xmlout)
    runner = wingtest_common.XmlTestRunner(result)
    plugin = CPytestPlugin(result, runner)
    try:
        import pytest
        # -s turns off stdout/err capturing
        # -p no:terminal turns off printing test result status to stdout
        # --tb=native gets parseable tracebacks on exceptions
        pytest.main(args=['-s', '-p', 'no:terminal', '--tb=native'] + sysargv + module_fullpath_list, plugins=[plugin])
    except SystemExit:
        raise
    except Exception:
        # Note that import error from test files end up here, so this is
        # not just for runner exceptions
        xmlout._write_exc_info(sys.exc_info())
        
if __name__ == '__main__':
    main(list(sys.argv))
