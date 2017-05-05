#########################################################################
""" Test runner for unittest

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

import sys
import unittest
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
    
def main(argv):

    our_dir = os.path.dirname(__file__)
    if sys.path[0] == our_dir:
        del sys.path[0]
        
    module_dir = wingtest_common.GetModuleDir(argv)

    process_per_module = wingtest_common.PopFromArgv(argv, '--one-module-per-process')
    
    pattern_list = []
    arg = wingtest_common.PopFromArgv(argv, '--pattern=')
    while arg is not None:
        pattern_list.append(arg[len('--pattern='):])
        arg = wingtest_common.PopFromArgv(argv, '--pattern=')
        process_per_module = True
        
    if len(pattern_list) != 0:
        return RunPatternList(argv, pattern_list, module_dir, process_per_module)
    
    if process_per_module:
        return RunModulesPerProcess(argv, module_dir)

    wingtest_common.SetupSysArgv(argv)
    xmlout = wingtest_common.CreateOutputStream(argv)
    sys.stdout = sys.stderr = xmlout
    try:
        RunInSingleDir(argv, xmlout, module_dir)
    finally:
        xmlout.finish()
        
def RunModulesPerProcess(argv, module_dir, first_call=True):
    """ Run each name in argv in it's own process.  Any arg beginning
    with a '-' is considered a flag and anything else is considered a name. """
    
    import subprocess

    # If --output-file is used, all child processes need to append to the
    # correct file
    
    flags = []
    names = []
    output_pathname = None
    
    append_flag = False
    for a in argv[1:]:
        if a.startswith('-'):
            if a.startswith('--output-file='):
                output_pathname = os.path.normpath(os.path.abspath(a[len('--output-file='):]))
                a = '--output-file=' + output_pathname
            elif a.startswith('--append-to-file'):
                append_flag = True
            flags.append(a)
        else:
            names.append(a)
        
    if output_pathname is not None:
        if not append_flag:
            if first_call:
                f = open(output_pathname, 'w')
                f.close()
            flags.append('--append-to-file')
            
    runner = os.path.normpath(os.path.abspath(sys.argv[0]))
    for name in names:
        if output_pathname is not None:
            print("Running module %s in %s" % (name, module_dir))
        child_argv = [sys.executable, runner] + flags + [name]
        subprocess.call(child_argv, cwd=module_dir)
        
def RunPatternList(argv, pattern_list, default_dir, module_per_process):        

    from glob import glob
    file_list = []
    for pattern in pattern_list:
        expanded = glob(pattern)
        file_list.extend(expanded)

    for i, filename in enumerate(file_list):
        dirname, basename = os.path.split(filename)
        if basename.lower().endswith('.py'):
            mod_name = basename[:-3]
        else:
            mod_name, ext = os.path.splitext(basename)

        mod_argv = list(argv) + [mod_name]
        if module_per_process:
            RunModulesPerProcess(mod_argv, dirname, first_call=(i == 0))
            
def RunInSingleDir(argv, xmlout, dirname):
    """ Run unittest TestProgram w/ given argv, first prepending dirname 
    to sys.path """
    
    saved_path = None
    if dirname != sys.path[0]:
        saved_path = list(sys.path)
        sys.path.insert(0, dirname)

    result = wingtest_common.XmlTestResult(xmlout)
    runner = wingtest_common.XmlTestRunner(result)
    try:
        try:
            unittest.TestProgram(argv=argv, module=None, testRunner=runner)
        except SystemExit:
            raise
        except Exception:
            # Note that import error from test files end up here, so this is
            # not just for runner exceptions
            xmlout._write_exc_info(sys.exc_info())
    finally:
        if saved_path is not None:
            sys.path = saved_path
        
if __name__ == '__main__':
    main(list(sys.argv))
