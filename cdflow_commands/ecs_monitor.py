from hashlib import sha1
from functools import lru_cache
from time import sleep, time

from cdflow_commands.logger import logger


def build_service_name(environment, component):
    service_name = '{}-{}'.format(environment, component)
    if len(service_name) > 32:
        service_name_hash = sha1(service_name.encode('utf-8')).hexdigest()
        service_name = '{}tf{}'.format(
            service_name[:24], service_name_hash[:4]
        )
    return service_name


class ECSMonitor():

    _TIMEOUT = 600
    _ITERATION_DELAY = 15

    def __init__(self, ecs_event_iterator):
        self._ecs_event_iterator = ecs_event_iterator

    def wait(self):
        start = time()
        for event in self._ecs_event_iterator:
            if time() - start > self._TIMEOUT:
                logger.error(
                    'Deployment timed out! '
                    'Didn\'t complete within {} seconds'.format(self._TIMEOUT)
                )
                raise TimeoutError
            if event.done:
                logger.info('Deployment complete')
                return True
            logger.info(
                'Deploying ECS tasks: desired {} running {}'.format(
                    event.desired, event.running
                )
            )

            sleep(self._ITERATION_DELAY)


class ECSEventIterator():

    def __init__(self, cluster, environment, component, version, boto_session):
        self._cluster = cluster
        self._environment = environment
        self._component = component
        self._version = version
        self._boto_session = boto_session
        self._done = False

    def __iter__(self):
        return self

    def __next__(self):
        if self._done:
            raise StopIteration

        primary_deployment = self._get_primary_deployment()
        release_image = self._get_release_image(
            primary_deployment['taskDefinition']
        )

        if release_image != '{}:{}'.format(self._component, self._version):
            raise ImageDoesNotMatchError

        running = primary_deployment['runningCount']
        desired = primary_deployment['desiredCount']
        if running != desired:
            return InProgressEvent(running, desired)

        self._done = True
        return DoneEvent(running, desired)

    @property
    def service_name(self):
        return build_service_name(self._environment, self._component)

    @property
    @lru_cache(maxsize=1)
    def _ecs(self):
        return self._boto_session.client('ecs')

    @lru_cache(maxsize=10)
    def _get_release_image(self, task_definition_arn):
        task_def = self._ecs.describe_task_definition(
            taskDefinition=task_definition_arn
        )['taskDefinition']['containerDefinitions'][0]

        return task_def['image'].split('/')[1]

    def _get_primary_deployment(self):
        services = self._ecs.describe_services(
            cluster=self._cluster,
            services=[self.service_name]
        )

        return [
            deployment
            for deployment in services['services'][0]['deployments']
            if deployment['status'] == 'PRIMARY'
        ][0]


class Event():

    def __init__(self, running, desired):
        self.running = running
        self.desired = desired


class DoneEvent(Event):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = True


class InProgressEvent(Event):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.done = False


class TimeoutError(Exception):
    pass


class ImageDoesNotMatchError(Exception):
    pass
