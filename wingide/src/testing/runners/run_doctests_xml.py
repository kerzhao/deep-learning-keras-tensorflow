#########################################################################
""" Test runner for doctests

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

Usage: run_doctests_xml.py [--directory=<dirname>] test-spec+

Each test-spec is a name composed of potentially 3 parts which are separated
by a colon (:) -- file-type:file-name:name-spec
  file-type: either 'python' or 'text'
  file-name: name of file; drive letter followed by : is included in name on win32
  name-spec: dotted name indicating which tests to run

"""
#########################################################################

import imp
import sys
import os.path
import doctest


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

EXAMPLE_PREFIX = 'Example #'
MODULE_TESTS_NAME = 'Module Tests'

xmlout = wingtest_common.CreateOutputStream(sys.argv)
sys.stdout = sys.stderr = xmlout


class _DummyDebugger:

    def __init__(self, *args, **kw):

        pass

    def __getattr__(self, name):

        def dummy(*args, **kw):
            pass

        return dummy

doctest._OutputRedirectingPdb = _DummyDebugger

class XmlDocTestRunner(doctest.DocTestRunner):

    def __init__(self, stream):

        doctest.DocTestRunner.__init__(self)
        self.stream = stream

    def report_start(self, out, test, example):

        name = test.name
        basefilename = os.path.basename(test.filename)
        if basefilename.lower().endswith('.py'):
            if name == '' or name == basefilename[:-3]:
                name = MODULE_TESTS_NAME
            elif name.startswith(basefilename[:-3] + '.'):
                name = name[len(basefilename[:-3] + '.'):]
        
        try:
            example_index = example.original_index
        except AttributeError:
            example_index = None
        if example_index is None:
            try:
                example_index = test.examples.index(example)
            except ValueError:
                example_index = 0

        example_name = EXAMPLE_PREFIX + str(example_index + 1)
        if name != '':
            name += '.' + example_name
        else:
            name = example_name

        if test.lineno is None or example.lineno is None:
            lineno = None
        else:
            lineno = test.lineno + example.lineno
        self.stream._start_test(name, test.filename, lineno=lineno)

    def report_success(self, out, text, example, got):

        if got[-1:] == '\n':
            got = got[:-1]
        self.stream.write(got)
        self.stream._finish_test('succeeded')

    def report_failure(self, out, text, example, got):

        if got[-1:] == '\n':
            got = got[:-1]
        self.stream.write(got)
        self.stream._finish_test('failed')

    def report_unexpected_exception(self, out, test, example, exc_info):

        self.stream._write_exc_info(exc_info)
        self.stream._finish_test('error')

def samefile(name1, name2):
    if sys.platform != 'win32':
        return os.path.samefile(name1, name2)
    
    name1 = os.path.normcase(os.path.normpath(os.path.abspath(name1)))
    name2 = os.path.normcase(os.path.normpath(os.path.abspath(name2)))
    return name1 == name2

class CDoctestRunner:
    
    def __init__(self, directory_name):
        
        self.directory_name = directory_name
        self.test_modules = []

    def load_tests_from_file(self, filename):
        
        local_name = os.path.basename(filename)
        mod_name = local_name.split('.')[0]
        dirname = os.path.dirname(filename)
        save_path = sys.path
        sys.path = [dirname] + list(save_path)
        try:
            mod = __import__(mod_name)
        finally:
            sys.path = save_path
        self.test_modules.append(mod)
        return mod
    
    def _parse_name(self, name):
        
        kind = 'python'
        
        parts = name.split(':')
        if parts[0] in ('python', 'text'):
            kind = parts[0]
            parts = parts[1:]
        
        filename = os.path.abspath(parts[0])
        if sys.platform == 'win32' and len(parts) >= 2 \
           and len(parts[0]) == 1 and parts[0].isalpha():
            filename = '%s:%s' % (parts[0], parts[1])
            parts = [filename] + parts[2:]
            
        if len(parts) == 1:
            return kind, filename, ''

        return kind, filename, parts[1]
        
    def __modify_test_for_example_specs(self, test, example_specs):
        """ Modify test.examples to contain only examples that match one of the
        example specs.  Returns None if none matches or test. """
        
        index_list = []
        for spec in example_specs:
            example_index = self.__get_example_index(spec)
            if example_index is not None and 0 <= example_index < len(test.examples):
                index_list.append(example_index)

        if len(index_list) == 0:
            return None
        index_list.sort()
        
        modified_list = []
        for example_index in index_list:
            example = test.examples[example_index]
            example.original_index = example_index
            modified_list.append(example)
        test.examples = modified_list

        return test
   
    def __get_example_index(self, n):
        
        if not n.startswith(EXAMPLE_PREFIX):
            return None
        try:
            return int(n[len(EXAMPLE_PREFIX):]) - 1
        except Exception:
            return None

    def _tests_from_text_file(self, filename):
        """ Load tests from a non-python text file. """
        
        f = open(filename, 'r')
        text = f.read()
        f.close()
        
        parser = doctest.DocTestParser()
        test = parser.get_doctest(text, {}, '', filename, 0)
        if test.name.startswith('.'):
            test.name = test.name[1:]
        return [test]
    
    def _tests_from_python_file(self, filename):
        """ Extract all tests from python file. """
        
        mod = self.load_tests_from_file(filename)
        if mod is None:
            return []
        
        finder = doctest.DocTestFinder(recurse=True)
        tests = finder.find(mod, module=mod, globs=mod.__dict__, name='')
        for t in tests:
            if t.name.startswith('.'):
                t.name = t.name[1:]

        return tests

    def __filter_single_test(self, test, name_specs):
        """ Return potentially modified tests if it matches. """

        matching_examples = []
        for name_spec in name_specs:
            parts = name_spec.split('.')
            if self.__get_example_index(parts[-1]) is not None:
                example_spec = parts[-1]
                name_spec = '.'.join(parts[:-1])
            else:
                example_spec = None
                
            if test.name == name_spec or test.name.startswith(name_spec + '.') \
               or (name_spec == MODULE_TESTS_NAME and test.name == ''):
                if example_spec is None:
                    return test
                else:
                    matching_examples.append(example_spec)

        if len(matching_examples) != 0:
            return self.__modify_test_for_example_specs(test, matching_examples)
        
        return None

    def __filter_tests(self, tests, name_specs):
        """ Return new list with tests that match the name_specs.  The name_specs
        list must be sorted. """
        
        if len(name_specs) == 0 or name_specs[0] == '':
            return tests

        filtered = []
        for test in tests:
            test = self.__filter_single_test(test, name_specs)
            if test is not None:
                filtered.append(test)
                
        return filtered

    def process_names(self, name_list):
        """ Process all names and run tests associated with them. """

        by_filename = {}
        for name in name_list:
            kind, filename, sub_name = self._parse_name(name)
            key = (kind, filename)
            if key not in by_filename:
                by_filename[key] = []
            by_filename[key].append(sub_name)
            
        tests = []
        for (kind, filename), name_specs in by_filename.items():
            name_specs.sort()
            if kind == 'python':
                file_tests = self._tests_from_python_file(filename)
            else:
                file_tests = self._tests_from_text_file(filename)
            tests.extend(self.__filter_tests(file_tests, name_specs))

        runner = XmlDocTestRunner(xmlout)
        for single_test in tests:
            runner.run(single_test, out=xmlout.write, clear_globs=True)
       
def main():

    # Set sys.path[0] directory so tests run as if test file was executed
    # Use --directory= value in sys.argv[0] or cwd; Note this is limited to
    # names representable in file system encoding
    dir_arg_prefix = '--directory='
    if len(sys.argv) > 1 and sys.argv[1][:len(dir_arg_prefix)] == dir_arg_prefix:
        module_dir = sys.argv[1][len(dir_arg_prefix):]
        del sys.argv[1]
    else:
        module_dir = os.getcwd()
        
    if module_dir is not None and os.path.isdir(module_dir):
        dirname = os.path.dirname(os.path.abspath(sys.argv[0]))
        if samefile(dirname, sys.path[0]):
            sys.path[0] = module_dir
        else:
            sys.path.insert(0, module_dir)


    finder = doctest.DocTestFinder()
    runner = CDoctestRunner(module_dir)

    name_list = []
    for arg in sys.argv[1:]:
        if not arg.startswith('-'):
            name_list.append(arg)

    wingtest_common.SetupSysArgv(sys.argv[:])

    try:
        runner.process_names(name_list)
    except SystemExit:
        raise
    except Exception:
        # Note that import error from test files might end up here
        xmlout._write_exc_info(sys.exc_info())
        
if __name__ == '__main__':
    try:
        main()
    finally:
        xmlout.finish()
        
