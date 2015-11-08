#!/usr/bin/python
# -*- coding: utf-8 -*-

"""updatedir - updates files from SLAVE to their newer versions from MASTER"""

from __future__ import print_function

__author__ = "Paweł Zacharek"
__copyright__ = "Copyright (C) 2015 Paweł Zacharek"
__date__ = "2015-11-06"
__license__ = "GPLv2+"
__version__ = "0.1.7"

import argparse
import os
import shutil
import sys

# parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("MASTER", help="master directory with actual version of software")
parser.add_argument("SLAVE", help="slave directory, where files will be copied")
parser.add_argument("BIN", help="rubbish bin for old versions of files")
parser.add_argument("-f", "--file", help="redirect output to a file")
parser.add_argument("-m", "--size", default="1GiB", help="max file size to store in BIN; default: 1GiB")
parser.add_argument("-s", "--script", action="store_true", help="only create shell script")
args = parser.parse_args()

binary_prefixes = {
	("KiB", 1024),
	("MiB", 1024**2),
	("GiB", 1024**3),
	("TiB", 1024**4),
	("PiB", 1024**5),
	("KB", 1000),
	("MB", 1000**2),
	("GB", 1000**3),
	("TB", 1000**4),
	("PB", 1024**5)
}

# collect all arguments in separate variables
try:
	MAX_FILE_SIZE = [value * int(args.size.rstrip(prefix)) for prefix, value in binary_prefixes if prefix in args.size][0]
except IndexError:
	MAX_FILE_SIZE = int(args.size)
MASTER = args.MASTER
SLAVE = args.SLAVE
BIN = args.BIN
FILE = args.file
SCRIPT = args.script

# make a list of files in both MASTER and SLAVE directories
PWD = os.getcwd()
os.chdir(MASTER)
master_listing = sorted(os.walk("."))
os.chdir(os.path.join(PWD, SLAVE))
slave_listing = sorted(os.walk("."))
os.chdir(PWD)

if FILE is not None:
	sys.stdout = open(FILE, "w")
if SCRIPT:
	print("#!/usr/bin/fish")

escape = lambda name: name.replace("'", r"\'")

def makedirs(name):
	print("mkdir -p '%s'" % escape(name))
	if not SCRIPT:
		os.makedirs(name)

def remove(name):
	print("rm '%s'" % escape(name))
	if not SCRIPT:
		os.remove(name)

def move(src, dst):
	print("mv '%s' '%s'" % (escape(src), escape(dst)))
	if not SCRIPT:
		shutil.move(src, dst)

def copy(src, dst):
	print("cp '%s' '%s'" % (escape(src), escape(dst)))
	if not SCRIPT:
		shutil.copy(src, dst)

def copytree(src, dst):
	print("cp -r '%s' '%s'" % (escape(src), escape(dst)))
	if not SCRIPT:
		shutil.copytree(src, dst)

# used for determining if a subdirectory has been copied
discarded_directories = []
already_copied = lambda directory: [parent for parent in discarded_directories if parent in directory]

# delete old files from SLAVE
m_root, _, m_files = master_listing[0]
master_index = 1
for s_root, s_dirs, s_files in slave_listing:
	# SLAVE and MASTER directories must be adjusted
	while master_index < len(master_listing) and m_root < s_root:
		m_root, _, m_files = master_listing[master_index]
		master_index += 1
	if m_root != s_root:  # this directory doesn't exist anymore
		if not already_copied(m_root):
			# looking for too large files, that won't be moved to the BIN
			for root, _, files in os.walk(os.path.join(SLAVE, s_root)):  # TODO: remove this os.walk()
				for file in files:
					if os.stat(os.path.join(root, file)).st_size > MAX_FILE_SIZE:  # file is too large
						remove(os.path.join(root, file))
			# create subdirectories in BIN
			if not os.path.isdir(os.path.join(BIN, s_root)):
				makedirs(os.path.join(BIN, s_root))
			# move all directory
			move(os.path.join(SLAVE, s_root), os.path.join(BIN, s_root))
			discarded_directories.append(s_root)
	else:  # the directory exist in MASTER
		for s_file in s_files:
			# moving old files to the BIN, depending on their size
			if s_file not in m_files or os.stat(os.path.join(MASTER, s_root, s_file)).st_mtime > os.stat(os.path.join(SLAVE, s_root, s_file)).st_mtime:
				if os.stat(os.path.join(SLAVE, s_root, s_file)).st_size > MAX_FILE_SIZE:
					remove(os.path.join(SLAVE, s_root, s_file))
				else:
					# create subdirectories in BIN
					if not os.path.isdir(os.path.join(BIN, s_root)):
						makedirs(os.path.join(BIN, s_root))
					# move single file
					move(os.path.join(SLAVE, s_root, s_file), os.path.join(BIN, s_root, s_file))
				# if we're in SCRIPT mode, we must handle the file right now, because it won't be deleted
				if SCRIPT and s_file in m_files:
					copy(os.path.join(MASTER, s_root, s_file), os.path.join(SLAVE, s_root, s_file))

# copy new files from MASTER to SLAVE
discarded_directories = []
s_root, _, s_files = slave_listing[0]
slave_index = 1
for m_root, m_dirs, m_files in master_listing:
	# SLAVE and MASTER directories must be adjusted
	while slave_index < len(slave_listing) and s_root < m_root:
		s_root, _, s_files = slave_listing[slave_index]
		slave_index += 1
	if s_root != m_root:  # in this case all directory must be copied
		if not already_copied(m_root):
			copytree(os.path.join(MASTER, m_root), os.path.join(SLAVE, m_root))
			discarded_directories.append(m_root)
	else:  # the directory exist in SLAVE
		for m_file in m_files:
			if not os.path.isfile(os.path.join(SLAVE, m_root, m_file)):  # NOTE: this action appears earlier in SCRIPT mode
				# old versions of files have been moved/deleted so far
				copy(os.path.join(MASTER, m_root, m_file), os.path.join(SLAVE, m_root, m_file))

if FILE is not None:
	sys.stdout.close()
