'''
PathwayGenie (c) University of Manchester 2017

PathwayGenie is licensed under the MIT License.

To view a copy of this license, visit <http://opensource.org/licenses/MIT/>.

@author:  neilswainston
'''
from threading import Thread
import json
import time

from ice.ice import IceThread
from parts_genie.parts import PartsThread
from plasmid_genie.plasmid import PlasmidThread


# from metabolomics_genie.metabolomics import MetabolomicsThread
class PathwayGenie(object):
    '''Class to run PathwayGenie application.'''

    def __init__(self):
        self.__status = {}
        self.__threads = {}
        self.__writers = {}

    def submit(self, data):
        '''Responds to submission.'''
        query = json.loads(data)

        # Do job in new thread, return result when completed:
        job_ids = []
        threads = _get_threads(query)

        for thread in threads:
            job_id = thread.get_job_id()
            job_ids.append(job_id)
            thread.add_listener(self)
            self.__threads[job_id] = thread

        # Start new Threads:
        thread_pool = ThreadPool(threads)
        thread_pool.start()

        return job_ids

    def get_progress(self, job_id):
        '''Returns progress of job.'''
        def _check_progress(job_id):
            '''Checks job progress.'''
            while (job_id not in self.__status or
                    self.__status[job_id]['update']['status'] == 'running'):
                time.sleep(1)

                if job_id in self.__status:
                    yield 'data:' + self.__get_response(job_id) + '\n\n'

            yield 'data:' + self.__get_response(job_id) + '\n\n'

        return _check_progress(job_id)

    def cancel(self, job_id):
        '''Cancels job.'''
        self.__threads[job_id].cancel()
        return job_id

    def event_fired(self, event):
        '''Responds to event being fired.'''
        self.__status[event['job_id']] = event

    def __get_response(self, job_id):
        '''Returns current progress for job id.'''
        return json.dumps(self.__status[job_id])


class ThreadPool(Thread):
    '''Basic class to run job Threads sequentially.'''

    def __init__(self, threads):
        self.__threads = threads
        Thread.__init__(self)

    def run(self):
        for thread in self.__threads:
            thread.start()
            thread.join()


def _get_threads(query):
    app = query.get('app', 'undefined')

    if app == 'PartsGenie':
        return [PartsThread(query, idx)
                for idx in range(len(query['designs']))]
    elif app == 'PlasmidGenie':
        return [PlasmidThread(query)]
    elif app == 'save':
        return [IceThread(query)]

    raise ValueError('Unknown app: ' + app)
