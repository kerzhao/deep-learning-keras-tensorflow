#########################################################################
""" Test runner for nose tests

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

import imp
import os.path
import sys


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

xmlout = wingtest_common.CreateOutputStream(sys.argv)
sys.stdout = sys.stderr = xmlout

import nose

class NoseTestResults(wingtest_common.XmlTestResult):
    """ Subclass for nose to handle differences from the stock unittest
    results, including:

    * SyntaxErrors and other exceptions occurring at the top level of a
      a module as it's loaded are turned into a fake test case that raise
      the exception when it is run.
    * If errorClasses doesn't exist, nose will monkeypatch this class and
      substitute some of its own methods
    * The test instances passed into the methods are wrappers around the
      unittest test instances.  The .test attribute is the unittest test
      instance
      """

    def __init__(self, stream):

        wingtest_common.XmlTestResult.__init__(self, stream)
        self.errorClasses = {}
        self.active_failure_case = None

    def startTest(self, test):

        if isinstance(test, nose.case.Failure) \
           or isinstance(test.test, nose.case.Failure):
            self.active_failure_case = test
        else:
            wingtest_common.XmlTestResult.startTest(self, test)

    def stopTest(self, test):

        if test == self.active_failure_case:
            self.active_failure_case = None
        else:
            wingtest_common.XmlTestResult.stopTest(self, test)


    def addError(self, test, err):

        if self.active_failure_case is not None:
            self.stream._write_exc_info(err)
            return

        code = self._getResultForExc(err)
        if code is not None:
            if code == 'SKIP':
                result = wingtest_common.SKIPPED
            else:
                # XXX is this always what is wanted?
                result = wingtest_common.SKIPPED + ':' + code
            self.stream.write_tag('result', result)
        else:
            wingtest_common.XmlTestResult.addError(self, test, err)

    def addFailure(self, test, err):
        if self.active_failure_case is not None:
            self.stream._write_exc_info(err)
            return
        
        code = self._getResultForExc(err)
        if code is not None:
            self.stream.write_tag('result', code)
        else:
            wingtest_common.XmlTestResult.addFailure(self, test, err)

    def _getResultForExc(self, exc_info):
        
        if exc_info is None:
            return None
        
        exc_type = exc_info[0]
        for item_type, item_detail in self.errorClasses.items():
            if issubclass(exc_type, item_type):
                return item_detail[1]
            
        return None
    
    def _testClassFilename(self, test):
        
        try:        
            inst = test.test.inst
        except AttributeError:
            pass
        else:
            return wingtest_common.XmlTestResult._testClassFilename(self, inst)
                
        try:
            proc, args = test.test._descriptors()
        except Exception:
            pass
        else:
            filename, lineno = self._getCodeLocation(proc)
            return filename
        
        # This is needed by the unreleased nose-py3k branch where test.test is 
        # a bare function
        if isinstance(test.test, type(main)):
            filename, lineno = self._getCodeLocation(test.test)
            return filename
            
        
        # First case is for stock nose in Python 2.x and second is for
        # newer nose versions
        try:
            t = test.test
        except:
            t = test
        
        return wingtest_common.XmlTestResult._testClassFilename(self, t)
        
    def _sourceCodeLocation(self, test):

        try:
            proc, args = test.test._descriptors()
        except Exception:
            pass
        else:
            return self._getCodeLocation(proc)
        
        return wingtest_common.XmlTestResult._sourceCodeLocation(self, test.test)
        
    def _testDottedName(self, test):
    
        name = wingtest_common.XmlTestResult._testDottedName(self, test.test)
        try:
            try:
                inst = test.test.inst
            except AttributeError:
                proc, args = test.test._descriptors()
                module_name = proc.__module__
            else:
                module_name = inst.__module__
        except Exception:
            module_name = None
        if module_name is not None and name.startswith(module_name + '.'):
            name = name[len(module_name) + 1:]
        return name
            
def main(argv):
    
    wingtest_common.SetupSysArgv(argv)
    
    dirname = wingtest_common.process_directory_arg(argv)
    
    # Assume all args not starting with - are filenames for tests
    for i, arg in enumerate(argv):
        if not arg.startswith('-') and not os.path.isabs(arg):
            argv[i] = os.path.join(dirname, arg)
    
    argv.append('--nocapture')
    
    result = NoseTestResults(sys.stdout)
    runner = wingtest_common.XmlTestRunner(result)
    try:
        try:
            nose.run(argv=argv, testRunner=runner)
        except SystemExit:
            raise
        except Exception:
            # Note that import error from test files end up here, so this is
            # not just for runner exceptions
            if isinstance(xmlout, wingtest_common.XmlStream):
                xmlout._write_exc_info(sys.exc_info())
            else:
                exc_type, exc, tb = sys.exc_info()
                sys.excepthook(exc_type, exc, tb)
    finally:
        xmlout.finish()
        
if __name__ == '__main__':
    main(list(sys.argv))


