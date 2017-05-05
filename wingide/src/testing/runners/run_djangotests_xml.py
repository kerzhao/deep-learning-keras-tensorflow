# coding:utf-8
#########################################################################
""" Run Django unit tests (both unittest and doctest tests)

Copyright (c) 1999-2012, Archaeopteryx Software, Inc.

Written by Stephan R.A. Deibel and John P. Ehresman

Thanks to Cédric RICARD for the initial version of this code

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
import unittest
import imp
import os

def get_tested_module(argv):
    for arg in argv[1:]:
        if not arg.startswith('-'):
            return arg

def get_project_dir_from_argv(argv):
    # Django <= 1.3 fall-back
    dir_arg_prefix = '--directory='
    if len(argv) > 1 and argv[1][:len(dir_arg_prefix)] == dir_arg_prefix:
        module_dir = argv[1][len(dir_arg_prefix):]
    else:
        module_dir = os.getcwd()
    return module_dir
    
def get_manage_dir_from_settings(settings_mod):
    # For Django 1.4+ only
    if '__init__.py' in settings_mod.__file__:
        p = os.path.dirname(settings_mod.__file__)
    else:
        p = settings_mod.__file__
    project_directory, settings_filename = os.path.split(p)
    if project_directory == os.curdir or not project_directory:
        project_directory = os.getcwd()
        
    return os.path.dirname(project_directory)
    
def init_django(argv):
    try:
        from django import VERSION
        if VERSION[0] == 1 and VERSION[1] < 4:
            django_lt_14 = True
        else:
            django_lt_14 = False
    except:
        django_lt_14 = True
        
    try:
        from django.conf import settings
        try:
            # Needed in Django 1.8+; not sure if it fails in earlier versions
            import django
            django.setup()
        except:
            pass
        from django.core.management import import_module
        module = import_module(settings.SETTINGS_MODULE)
        if django_lt_14:
            from django.core.management import setup_environ
            manage_dir = setup_environ(module, settings.SETTINGS_MODULE)
        else:
            manage_dir = get_manage_dir_from_settings(module)
    except:
        project_dir = get_project_dir_from_argv(argv)
        sys.path.insert(0, os.path.abspath(project_dir))
        sys.path.append(os.path.abspath(os.path.join(project_dir, '..')))
        import settings
        if django_lt_14:
            from django.core.management import setup_environ
            manage_dir = setup_environ(settings)
        else:
            manage_dir = get_manage_dir_from_settings(settings)
        
    return manage_dir
    
def main(argv):
    sys.stderr.write(str(argv) + '\n')
    
    # XXX Hack to allow setting a different settings module for testing only
    if 'WING_TEST_DJANGO_SETTINGS_MODULE' in os.environ:
        os.environ['DJANGO_SETTINGS_MODULE'] = os.environ['WING_TEST_DJANGO_SETTINGS_MODULE']
        
    f, filename, info = imp.find_module('wingtest_common', [os.path.dirname(__file__)])
    try:
        wingtest_common = imp.load_module('wingtest_common', f, filename, info)
    finally:
        f.close()
        
    if 0:
        import wingtest_common
        
    class CDjangoXMLTestResult(wingtest_common.XmlTestResult):
        
        def startTest(self, test):
            unittest.TestResult.startTest(self, test)
            class_filename = self._testClassFilename(test)
            code_filename, lineno = self._sourceCodeLocation(test)
            if hasattr(test, '_dt_test'):
                name = test.id()
                if name.startswith('django.contrib.'):
                    name = name[len('django.contrib.'):]
                else:
                    parts = name.split('.')
                    name = '.'.join(parts[1:])
                parts = name.split('.')
                if '__test__' in name:
                    new_parts = []
                    for i, part in enumerate(parts):
                        if i+1 < len(parts) and parts[i+1] == '__test__':
                            pass
                        else:
                            new_parts.append(part)
                    name = '.'.join(new_parts)
                else:
                    name = '.'.join(parts[:-1]) + '.__test__'
            else:
                name = self._testDottedName(test)
            self.stream._start_test(name, class_filename,
                                    code_filename=code_filename, lineno=lineno)
            
        def _sourceCodeLocation(self, test):
            if hasattr(test, '_dt_test'):
                if not test._dt_test.lineno:
                    lineno = 0
                else:
                    lineno = test._dt_test.lineno
                return test._dt_test.filename, lineno
            else:
                return wingtest_common.XmlTestResult._sourceCodeLocation(self, test)

    testedModule = get_tested_module(argv)
    if testedModule.endswith('.__test__'):
        testedModule = testedModule[:-len('.__test__')]
    testedModuleList = testedModule and testedModule.split('.') or []
    manage_dir = init_django(argv)
    
    class MyXmlStream(wingtest_common.XmlStream):
        def _start_test(self, name, filename, lineno=None, code_filename=None):
            testPath, testFilename = os.path.split(filename)
            testPath = os.path.normpath(testPath)
            if testFilename == 'tests.py':
                appName = os.path.basename(testPath)
            else:
                appName = os.path.basename(os.path.dirname(testPath))
            if name.find('__test__') == -1 and appName != 'django':
                testname = '%s.%s' % (appName, name)
            else:
                testname = name
                if testname.endswith('__test__'):
                    parts = testname.split('.')
                    if len(parts) > 1:
                        testname = '.'.join(parts[:-1])
            sys.stderr.write('test: %s' % testname)
            
            super(MyXmlStream, self)._start_test(testname, os.path.join(manage_dir, 'manage.py'), 
                                                 lineno-1, code_filename)
                             
    xmlout = wingtest_common.CreateOutputStream(argv, xml_stream_cls=MyXmlStream)
    sys.stdout = sys.stderr = xmlout

    wingtest_common.process_directory_arg(argv)
    
    result = CDjangoXMLTestResult(sys.stdout)
    
    testedModule = '.'.join(testedModuleList[1:])
    test_labels = testedModule and [testedModule] or []
    # Add 'test' to sys.argv since some code uses it to decide if 
    # it's being tested or just run
    sys.argv = [os.path.join(manage_dir, 'manage.py'), 'test'] + test_labels
    sys.stderr.write(str(sys.argv) + '\n')
    
    from django.conf import settings
    try:
        from django.test.simple import DjangoTestRunner, DjangoTestSuiteRunner
        test_base = DjangoTestRunner
    except:
        try:
            # Django <= 1.7
            from django.test.simple import DjangoTestSuiteRunner
        except:
            # Django 1.8+
            import django
            django.setup()
            from django.test.utils import get_runner
            DjangoTestSuiteRunner = get_runner(settings)
        from unittest import TextTestRunner
        test_base = TextTestRunner

    # South (schema migration tool) does not use the 'test' command anymore
    if 'south' in settings.INSTALLED_APPS:

        try:
            # Older versions of South had this layout
            from south.management.commands.test import MigrateAndSyncCommand
        except ImportError:
            from south.management.commands import MigrateAndSyncCommand
        from django.core import management
        management.get_commands()
        
        # Point at the core syncdb command when creating tests; tests should
        # always be up to date with the most recent model structure
        if hasattr(settings, "SOUTH_TESTS_MIGRATE") and not settings.SOUTH_TESTS_MIGRATE:
            management._commands['syncdb'] = 'django.core'
        else:
            management._commands['syncdb'] = MigrateAndSyncCommand()
        
    class MyTestRunner(test_base):
        def __init__(self, testResult, **kwargs):
            super(MyTestRunner, self).__init__(**kwargs)
            self.testResult = testResult
            
        def _makeResult(self):
            return self.testResult

    class MyTestSuiteRunner(DjangoTestSuiteRunner):
        def __init__(self, testResult, **kwargs):
            super(MyTestSuiteRunner, self).__init__(**kwargs)
            self.testResult = testResult
            
        def run_suite(self, suite, **kwargs):
            return MyTestRunner(self.testResult, verbosity=self.verbosity, failfast=self.failfast).run(suite)
    
    runner = MyTestSuiteRunner(result, verbosity=0, interactive=False)
    try:
        try:
            failures = runner.run_tests(test_labels)
        except SystemExit:
            raise
        except Exception:
            # Note that import error from test files might end up here
            if isinstance(xmlout, MyXmlStream):
                xmlout._write_exc_info(sys.exc_info())
            else:
                exc_type, exc, tb = sys.exc_info()
                sys.excepthook(exc_type, exc, tb)
    finally:
        xmlout.finish()
        
if __name__ == '__main__':
    main(list(sys.argv))
