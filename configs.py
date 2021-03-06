#!/usr/bin/env python
#
# Copyright (c) 2014 Marek Chalupa
# E-mail: statica@fi.muni.cz
#
# Permission to use, copy, modify, distribute, and sell this software and its
# documentation for any purpose is hereby granted without fee, provided that
# the above copyright notice appear in all copies and that both that copyright
# notice and this permission notice appear in supporting documentation, and
# that the name of the copyright holders not be used in advertising or
# publicity pertaining to distribution of the software without specific,
# written prior permission. The copyright holders make no representations
# about the suitability of this software for any purpose. It is provided "as
# is" without express or implied warranty.
#
# THE COPYRIGHT HOLDERS DISCLAIM ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
# INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN NO
# EVENT SHALL THE COPYRIGHT HOLDERS BE LIABLE FOR ANY SPECIAL, INDIRECT OR
# CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE,
# DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
# TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.
#
# On arran we have only python2, so use python2

import sys
import os
import getopt
import time

allowed_keys = ['tool-dir', 'remote-dir', 'benchmarks', 'machines',
                'ssh-user', 'ssh-cmd', 'cmd', 'sync', 'timeout',
                'no-db', 'sync-cmd', 'year', 'params', 'exclude', 'note',
                'tool-tag']

def usage():
    sys.stderr.write(
"""
Static analysis tools tester, 2014 - 2015
-------------------------------------

Usage: satt [OPTS] [tool]

OPTS can be:
    --machines=file.txt             File with machines
    --benchmarks=dir/set_file       Directory with sets of benchmarks or set file(s)
    --no-sync                       Do not sync tool on remote machines
    --sync=[yes/no]                 Whether to sync tool on remote machines
    --debug                         Enable debugging messages
    --no-db                         Do not store result to database
    --year=[year]                   Specify year (git tag i. e. master, svcomp15, ...)
    --save-new-task                 Create new tasks if they are not in database
    --ignore-duplicates             Ignore duplicate results for tasks
    --exclude=set1.set,set2.set,... Do not run these benchmark sets. Ignored when
                                    standalone .set file is given in --benchmarks
                                    (applies only on directories).
    --params=[params]               overrides params entry in config file
    --note=[note]                   add note about this run of satt (will have effect
                                    only without --no-db)
    --no-email                      do not send e-mail after completition (the e-mail
                                    is sent only when running on all benchmarks)
    --tool-tag=tag                  tag for the tool to filter it in database
    --skip-known-benchmarks=ID      skip benchmarks for which we already have result in
                                    the db (for tool with id ID)
These options can be specified in config file (except for 'debug' and 'no-db')

Each tool is supposed to have its own directory with config files and
scripts that will run the tool on remote computers. Basically, all that
is needed is:
tool_dir  \
    config
    remote_runner
    remote_sync (optional)

In config file, there are few keys that are searched for:
tool-dir      -- directory that contains the tool
remote-dir    -- where will we work on remote machines
cmd           -- command to run for each benchmark. This command is run as given
                 (on local computer), therfore to run a test on remote computer,
		 the command will probably call ssh
timeout       -- timeout for tests
sync-cmd      -- run this command before running tests to sync tool and benchmarks
                 on remote computers
year          -- specify year of sv-comp. The benchmarks will be checked out to this tag

There are two special variables {benchmark} (synonym {file}) and {machine}
that will expand to current benchmark file and remote machine.

Command-line argument have higher priority. Tool defaults to 'symbiotic'

Database is supposed to have configuration in database/config with following format:
host=[host]
user=[user]
password=[passwd]
db=[database]

Allowed keys in config file:
""")

    i = 0
    for k in allowed_keys:
        sys.stderr.write(k)

        i += 1
        if i % 3 == 0:
            sys.stderr.write('\n')
        else:
            sys.stderr.write('\t')


# fill in default values
configs = {'sync':'yes', 'ssh-user':'', 'remote-dir':'',
           'cmd':'echo "No command specified for file: {file}"',
           'no-db':'no', 'debug':'no', 'tool':'symbiotic',
           'year':'master', 'params':{'*':''}, 'exclude':'',
           'started_at' : time.strftime('%Y-%m-%d-%H-%S'), 'note':'',
           'save-new-tasks' : 'no', 'ignore-duplicates' : 'no',
           'send-email' : 'yes', 'skip-known-benchmarks' : 'no'}

def params_from_string(pars, pard = None):
    " pars = params string, pard = params dictionary "
    " returns updated (or new) dictionary created from params string"

    # default value for all benchmarks is empty string
    # this way we avoid exceptions without explicit checks
    if pard is None:
        pard = {'*':''}

    for p in pars.split(','):
        try:
            k, v = p.split(':', 1)
        except ValueError:
            from common import err
            err('Wrong item in params key: {0}'.format(p))

        k = k.strip()

        # allow omit *
        if not k:
            k = '*'

        pard[k] = v.strip()

    return pard

def parse_configs(path = 'symbiotic/config'):
    from common import err, dbg

    if not os.path.exists(path):
        return configs

    try:
        f = open(path, 'r')
    except IOError as e:
        err("Failed opening configuration file ({0}): {1}"
            .format(path, e.strerror))

    accline = None

    for line in f:
        line = line.strip()

        if not line or line[0] == '#':
            continue

        if not accline is None:
            line = accline + line
            accline = None

        # if \ is on the end of line, append next line
        if line[-1] == '\\':
            accline = line[:-1]
            continue

        key, val = line.split('=', 1)
        key = key.strip()
        val = val.strip()

        if key in allowed_keys:
            if key == 'params':
                configs[key] = params_from_string(val)
            else:
                configs[key] = val
        else:
            err('Unknown config key: {0}'.format(key))

    return configs

def parse_command_line():
    from common import err, dbg

    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                  ['help', 'machines=', 'benchmarks=',
                                   'no-sync', 'no-db', 'sync=', 'debug',
                                   'year=', 'exclude=', 'params=', 'note=',
                                   'save-new-tasks', 'ignore-duplicates',
                                   'no-email', 'tool-tag=', 'skip-known-benchmarks='])

    except getopt.GetoptError as e:
        err('{0}'.format(str(e)))

    for opt, arg in opts:
        if opt == '--help':
            usage()
            sys.exit(1)
        elif opt == '--machines':
            configs['machines'] = arg
        elif opt == '--benchmarks':
            configs['benchmarks'] = arg
        elif opt == '--no-sync':
            configs['sync'] = 'no'
        elif opt == '--sync':
            configs['sync'] = arg
        elif opt == '--no-db':
            configs['no-db'] = 'yes'
        elif opt == '--save-new-tasks':
            configs['save-new-tasks'] = 'yes'
        elif opt == '--ignore-duplicates':
            configs['ignore-duplicates'] = 'yes'
        elif opt == '--debug':
            configs['debug'] = 'yes'
        elif opt == '--year':
            configs['year'] = arg
        elif opt == '--exclude':
            configs['exclude'] = arg
        elif opt == '--note':
            configs['note'] = arg
        elif opt == '--tool-tag':
            configs['tool-tag'] = arg
        # this switch takes int argument just due
        # to technicall constrains. The tool id we can infer after
        # we got the result, but we don't want to run it at all
        elif opt == '--skip-known-benchmarks':
            configs['skip-known-benchmarks'] = arg
        elif opt == '--no-email':
            configs['send-email'] = 'no'
        elif opt == '--params':
            if configs.has_key('params'):
                # if we have some params, just update
                configs['params'] = params_from_string(arg, configs['params'])
            else:
                configs['params'] = params_from_string(arg)
        else:
            err('Unknown switch {0}'.format(opt))

    if len(args) > 1:
        usage()
        sys.exit(1)
    elif len(args) == 1:
        configs['tool'] = args[0]

    # print debug
    for l, r in configs.items():
        dbg('{0} = {1}'.format(l, r))

    return configs['tool']
