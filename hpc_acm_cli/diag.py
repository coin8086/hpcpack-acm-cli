from __future__ import print_function
import time
import datetime
import sys
import json
from hpc_acm.rest import ApiException
from hpc_acm_cli.command import Command
from hpc_acm_cli.utils import print_table, match_names, arrange

class Diagnostics(Command):
    @classmethod
    def profile(cls):
        return {
            'description': '''
HPC diagnostic client for querying/creating/canceling diagnostic jobs.
For help of a subcommand(tests|list|show|new|cancel), execute "%(prog)s {subcommand} -h"
    '''
        }

    @classmethod
    def subcommands(cls, config):
        return [
            {
                'name': 'tests',
                'help': 'list available diagnostic tests',
            },
            {
                'name': 'list',
                'help': 'list diagnostic jobs',
                'params': [
                    {
                        'name': '--count',
                        'options': {
                            'help': 'number of jobs to query',
                            'type': int,
                            'default': config.getint('DEFAULT', 'count', fallback=None)
                        }
                    },
                    {
                        'name': '--last-id',
                        'options': { 'help': 'the job id since which(but not included) to query' }
                    },
                    {
                        'name': '--asc',
                        'options': { 'help': 'query in id-ascending order', 'action': 'store_true' }
                    },
                ],
            },
            {
                'name': 'show',
                'help': 'show a diagnostic job',
                'params': [
                    {
                        'name': 'id',
                        'options': { 'help': 'job id', }
                    },
                    {
                        'name': '--wait',
                        'options': { 'help': 'wait a job until it\'s over', 'action': 'store_true' }
                    },
                ],
            },
            {
                'name': 'new',
                'help': 'create a new diagnotic job',
                'params': [
                    {
                        'group': True,
                        'items': [
                            {
                                'name': '--nodes',
                                'options': {
                                    'help': 'names of nodes to be tested. Either this or the --pattern parameter must be provided.',
                                    'metavar': 'node',
                                    'nargs': '+'
                                }
                            },
                            {
                                'name': '--pattern',
                                'options': {
                                    'help': 'name pattern of nodes to be tested. Either this or the --nodes parameter must be provided.',
                                    'default': config.get('DEFAULT', 'pattern', fallback=None)
                                }
                            },
                        ]
                    },
                    {
                        'name': 'test',
                        'options': {
                            'help': 'test to run, e.g. "mpi-pingpong". For available tests, resort to the "tests" subcommand.',
                        }
                    },
                ],
            },
            {
                'name': 'cancel',
                'help': 'cancel a job',
                'params': [
                    {
                        'name': 'ids',
                        'options': { 'help': 'job id', 'metavar': 'id', 'nargs': '+' }
                    },
                ],
            },
        ]

    def tests(self):
        tests = self.api.get_diagnostic_tests()
        self.print_tests(tests)

    def list(self):
        jobs = self.api.get_diagnostic_jobs(reverse=not self.args.asc, count=self.args.count, last_id=self.args.last_id)
        self.print_jobs(jobs)

    def show(self):
        job = self.api.get_diagnostic_job(self.args.id)
        if self.args.wait:
            state = job.state
            while not state in ['Finished', 'Failed', 'Canceled']:
                sys.stdout.write('.')
                sys.stdout.flush()
                time.sleep(1)
                job = self.api.get_diagnostic_job(self.args.id)
                state = job.state
            print('\n')
        self.print_jobs([job])
        try:
            result = self.api.get_diagnostic_job_aggregation_result(self.args.id)
        except ApiException: # 404 when aggregation result is not ready
            result = None
        if result:
            self.print_agg_result(job, result)

    def new(self):
        if self.args.nodes:
            nodes = self.args.nodes
        elif self.args.pattern:
            all = self.api.get_nodes(count=1000000)
            names = [n.name for n in all]
            nodes = match_names(names, self.args.pattern)
        else:
            raise ValueError('Either nodes or pattern parameter must be provided!')

        cat, name = self.args.test.split('-')
        job = {
            "targetNodes": nodes,
            "diagnosticTest": {
                "name": name,
                "category": cat,
            },
        }
        job = self.api.create_diagnostic_job(job = job)
        self.print_jobs([job])

    def cancel(self):
        for id in self.args.ids:
            try:
                self.api.cancel_diagnostic_job(id, job = { "request": "cancel" })
                print("Job %s is canceled." % id)
            except ApiException as e:
                print("Failed to cancel job %s. Error:\n" % id, e)

    def print_tests(self, tests):
        test = {
            'title': 'Test',
            'value': lambda t: '%s-%s' % (t.category, t.name)
        }
        description = {
            'title': 'Description',
            'value': lambda t: arrange(t.description, 80),
        }
        print_table([test, description], tests)

    def print_jobs(self, jobs):
        target_nodes = {
            'title': 'Target nodes',
            'value': lambda j: len(j.target_nodes)
        }
        test = {
            'title': 'Test',
            'value': lambda j: '%s-%s' % (j.diagnostic_test.category, j.diagnostic_test.name)
        }
        print_table(['id', test, 'state', target_nodes, 'created_at'], jobs)

    def print_agg_result(self, job, result):
        if isinstance(result, str):
            result = json.loads(result)
        if job.diagnostic_test.category == 'mpi' and job.diagnostic_test.name == 'pingpong':
            self.print_mpi_pingpong_result(result)
        else:
            print('Aggregation result:')
            json.dump(result, sys.stdout, indent=4)
            print()

    def print_mpi_pingpong_result(self, result):
        def get_and_print(field):
            nodes = result.get(field, None)
            if nodes is not None:
                nodes.sort()
                print("%s(%d):" % (field, len(nodes)))
                for n in nodes:
                    print(n)
        get_and_print("GoodNodes")
        get_and_print("BadNodes")

def main():
    Diagnostics.run()

if __name__ == '__main__':
    main()

