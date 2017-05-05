#coding:utf-8
#########################################################################
""" _patchsupport.py -- support for finding patch dirs that may be imported
or exec'd by debug components

Copyright (c) 1999-2017, Archaeopteryx Software, Inc.  All rights reserved.

Written by Stephan R.A. Deibel and John P. Ehresman
 
"""
#########################################################################

import sys
import os

# Wing version & build numbers
kVersion = "6.0.4"
kBuild = "1"
kProduct = "Pro"

def FindWingVersionString():
  """ Returns version string. """

  if kBuild[:1] == 'b' or kBuild[:2] == 'rc':
    return kVersion + kBuild
  else:
    return kVersion

def GetProbableUserSettings():
  """ Return user settings dirname; may be incorrect on win32 if env is
  screwed up. """
  
  major_version = kVersion.split('.')[0]
  if kProduct == 'Pro':
    windir = 'Wing IDE ' + major_version
    osxdir = 'Wing IDE/v' + major_version
    posixdir = '.wingide' +  major_version
  elif kProduct == 'Personal':
    windir = 'Wing Personal ' + major_version
    osxdir = 'Wing Personal/v' + major_version
    posixdir = '.wingpersonal' + major_version
  else:
    assert kProduct == '101'
    windir = 'Wing 101 ' + major_version
    osxdir = 'Wing 101/v' + major_version
    posixdir = '.wing101-' + major_version  

  try:
    if sys.platform == 'win32':
      return '%s\\%s' % (os.environ['APPDATA'], windir)
    elif sys.platform == 'darwin':
      return '%s/Library/Application Support/%s' % (os.environ['HOME'], osxdir)
    else:
      return '%s/%s' % (os.environ['HOME'], posixdir)
  except KeyError:
    return None

def FindAllPatchDirs(winghome, user_settings):
  """ Get list of all patch dirs, with highest patch #'s first.  Pass in
  user_settings=None to use probable dir or user_settings='' to ignore
  user settings dir. """

  wing_version = FindWingVersionString()
  if wing_version is None:
    return []

  if user_settings is None:
    user_settings = GetProbableUserSettings()

  patch_dirs = []
  if winghome is not None and winghome != '' and os.path.isdir(winghome):
    patch_dirs.append(os.path.join(winghome, 'patches', wing_version))
  if user_settings is not None and user_settings != '' \
     and os.path.isdir(user_settings):
    patch_dirs.append(os.path.join(user_settings, 'patches', wing_version))

  pair_list = []
  for dirname in patch_dirs:
    try:
      name_list = os.listdir(dirname)
    except (OSError, IOError):
      pass
    else:
      for name in name_list:
        pair_list.append((name, os.path.join(dirname, name)))
        
  pair_list.sort()
  pair_list.reverse()
  
  dir_list = []
  for name, dirname in pair_list:
    dir_list.append(dirname)
  return dir_list

def FindMatching(pathname, winghome, user_settings=None, patch_dirs=None):
  """ Find list of filenames where pathname exists within a patch dir. """
  
  if os.path.isabs(pathname):
    return []
  if patch_dirs is None:
    patch_dirs = FindAllPatchDirs(winghome, user_settings)
  if not patch_dirs:
    return []

  matching = []
  for dirname in patch_dirs:
    fullname = os.path.join(dirname, pathname)
    if os.path.exists(fullname):
      matching.append(fullname)
      
  return matching
