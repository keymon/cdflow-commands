from subprocess import check_call
from collections import namedtuple


DeployConfig = namedtuple('DeployConfig', [
    'account_prefix',
    'team',
    'account_id'
])


class Deploy(object):

    def __init__(
        self, boto_session, component_name, environment_name,
        version, config
    ):
        self._boto_session = boto_session
        self._aws_region = boto_session.region_name
        self._component_name = component_name
        self._environment_name = environment_name
        self._version = version
        self._config = config

    @property
    def _image_name(self):
        return '{}.dkr.ecr.{}.amazonaws.com/{}:{}'.format(
            self._config.account_id,
            self._aws_region,
            self._component_name,
            self._version
        )

    @property
    def _terragrunt_parameters(self):
        return [
            '-var', 'component={}'.format(self._component_name),
            '-var', 'aws_region={}'.format(self._aws_region),
            '-var', 'env={}'.format(self._environment_name),
            '-var', 'image={}'.format(self._image_name),
            '-var', 'team={}'.format(self._config.team),
            '-var', 'version={}'.format(self._version)
        ]

    def run(self):
        check_call(['terraform', 'get', 'infra'])

        credentials = self._boto_session.get_credentials()
        env = {
            'AWS_ACCESS_KEY_ID': credentials.access_key,
            'AWS_SECRET_ACCESS_KEY': credentials.secret_key,
            'AWS_SESSION_TOKEN': credentials.token
        }

        check_call(
            ['terragrunt', 'plan', 'infra'] + self._terragrunt_parameters,
            env=env
        )
        check_call(
            ['terragrunt', 'apply', 'infra'] + self._terragrunt_parameters,
            env=env
        )
