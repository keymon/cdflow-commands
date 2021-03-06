import unittest
from string import ascii_letters, printable

from boto3 import Session

from cdflow_commands.plugins.ecs import Deploy, DeployConfig
from hypothesis import given
from hypothesis.strategies import dictionaries, fixed_dictionaries, text
from mock import ANY, patch

IGNORED_PARAMS = [ANY] * 18
CALL_KWARGS = 2


class TestDeploy(unittest.TestCase):

    def setUp(self):
        # Given
        boto_session = Session(
            'dummy-access-key', 'dummy-secreet-access-key',
            'dummy-session-token', 'eu-west-1'
        )
        self._deploy_config = DeployConfig(
            'dummy-team', 'dummy-account-id', 'dummy-platform-config-file'
        )
        self._deploy = Deploy(
            boto_session, 'dummy-component', 'dummy-env',
            'dummy-version', 'dummy-ecs-cluster', self._deploy_config
        )

    @patch('cdflow_commands.plugins.ecs.check_call')
    @patch('cdflow_commands.plugins.ecs.get_secrets')
    @patch('cdflow_commands.plugins.ecs.NamedTemporaryFile')
    def test_terraform_modules_fetched(
        self, NamedTemporaryFile, get_secrets, check_call
    ):
        # When
        NamedTemporaryFile.return_value.__enter__.return_value.name = ANY
        get_secrets.return_value = {}
        self._deploy.run()
        # Then
        check_call.assert_any_call(['terragrunt', 'get', 'infra'])

    @patch('cdflow_commands.plugins.ecs.check_call')
    @patch('cdflow_commands.plugins.ecs.get_secrets')
    @patch('cdflow_commands.plugins.ecs.NamedTemporaryFile')
    def test_terragrunt_plan_called(
        self, NamedTemporaryFile, get_secrets, check_call
    ):
        # When
        NamedTemporaryFile.return_value.__enter__.return_value.name = ANY
        get_secrets.return_value = {}
        self._deploy.run()
        # Then
        check_call.assert_any_call(
            ['terragrunt', 'plan'] + IGNORED_PARAMS + ['infra'],
            env=ANY
        )

    @patch('cdflow_commands.plugins.ecs.check_call')
    @patch('cdflow_commands.plugins.ecs.get_secrets')
    @patch('cdflow_commands.plugins.ecs.NamedTemporaryFile')
    def test_terrgrunt_apply_called(
        self, NamedTemporaryFile, get_secrets, check_call
    ):
        # When
        NamedTemporaryFile.return_value.__enter__.return_value.name = ANY
        get_secrets.return_value = {}
        self._deploy.run()
        # Then
        check_call.assert_any_call(
            ['terragrunt', 'apply'] + IGNORED_PARAMS + ['infra'],
            env=ANY
        )

    credentials = fixed_dictionaries({
        'access_key_id': text(alphabet=printable, min_size=20, max_size=20),
        'secret_access_key': text(
            alphabet=printable, min_size=40, max_size=40
        ),
        'session_token': text(alphabet=printable, min_size=20, max_size=20)
    })

    @given(credentials)
    def test_terragrunt_passed_aws_credentials_from_session(
        self, credentials
    ):
        # Given
        boto_session = Session(
            credentials['access_key_id'],
            credentials['secret_access_key'],
            credentials['session_token'],
            'eu-west-10'
        )
        deploy = Deploy(boto_session, ANY, ANY, ANY, ANY, self._deploy_config)

        with patch(
            'cdflow_commands.plugins.ecs.check_call'
        ) as check_call, patch(
            'cdflow_commands.plugins.ecs.NamedTemporaryFile', autospec=True
        ) as NamedTemporaryFile, patch(
            'cdflow_commands.plugins.ecs.get_secrets'
        ) as get_secrets:
            NamedTemporaryFile.return_value.__enter__.return_value.name = ANY
            get_secrets.return_value = {}

            # When
            deploy.run()

            # Then
            check_call.assert_any_call(
                ['terragrunt', 'plan'] + IGNORED_PARAMS + ['infra'],
                env=ANY
            )
            plan_env = check_call.mock_calls[1][CALL_KWARGS]['env']
            assert plan_env['AWS_ACCESS_KEY_ID'] == \
                credentials['access_key_id']
            assert plan_env['AWS_SECRET_ACCESS_KEY'] == \
                credentials['secret_access_key']
            assert plan_env['AWS_SESSION_TOKEN'] == \
                credentials['session_token']

            check_call.assert_any_call(
                ['terragrunt', 'apply'] + IGNORED_PARAMS + ['infra'],
                env=ANY
            )
            apply_env = check_call.mock_calls[2][CALL_KWARGS]['env']
            assert apply_env['AWS_ACCESS_KEY_ID'] == \
                credentials['access_key_id']
            assert apply_env['AWS_SECRET_ACCESS_KEY'] == \
                credentials['secret_access_key']
            assert apply_env['AWS_SESSION_TOKEN'] == \
                credentials['session_token']

    @given(dictionaries(
        keys=text(alphabet=printable), values=text(alphabet=printable)
    ))
    def test_terragrunt_passed_copy_of_local_process_environment(
        self, mock_environment
    ):
        # Given
        boto_session = Session(
            'dummy-access_key_id',
            'dummy-secret_access_key',
            'dummy-session_token',
            'eu-west-10'
        )

        deploy = Deploy(boto_session, ANY, ANY, ANY, ANY, self._deploy_config)

        with patch(
            'cdflow_commands.plugins.ecs.os'
        ) as mock_os, patch(
            'cdflow_commands.plugins.ecs.check_call'
        ) as check_call, patch(
            'cdflow_commands.plugins.ecs.NamedTemporaryFile', autospec=True
        ) as NamedTemporaryFile, patch(
            'cdflow_commands.plugins.ecs.get_secrets'
        ) as get_secrets:
            NamedTemporaryFile.return_value.__enter__.return_value.name = ANY
            get_secrets.return_value = {}
            mock_os.environ = mock_environment.copy()
            aws_env_vars = {
                'AWS_ACCESS_KEY_ID': 'dummy-access_key_id',
                'AWS_SECRET_ACCESS_KEY': 'dummy-secret_access_key',
                'AWS_SESSION_TOKEN': 'dummy-session_token'
            }
            expected_environment = {**mock_environment, **aws_env_vars}

            # When
            deploy.run()
            # Then
            check_call.assert_any_call(
                ['terragrunt', 'plan'] + IGNORED_PARAMS + ['infra'],
                env=expected_environment
            )
            check_call.assert_any_call(
                ['terragrunt', 'apply'] + IGNORED_PARAMS + ['infra'],
                env=expected_environment
            )

    @given(dictionaries(
        keys=text(alphabet=printable), values=text(alphabet=printable)
    ))
    def test_terragrunt_does_not_mutate_local_process_environment(
        self, mock_environment
    ):
        # Given
        boto_session = Session(
            'dummy-access_key_id',
            'dummy-secret_access_key',
            'dummy-session_token',
            'eu-west-10'
        )

        deploy = Deploy(boto_session, ANY, ANY, ANY, ANY, self._deploy_config)

        with patch(
            'cdflow_commands.plugins.ecs.os'
        ) as mock_os, patch(
            'cdflow_commands.plugins.ecs.check_call'
        ), patch(
            'cdflow_commands.plugins.ecs.NamedTemporaryFile', autospec=True
        ) as NamedTemporaryFile, patch(
            'cdflow_commands.plugins.ecs.get_secrets'
        ) as get_secrets:
            NamedTemporaryFile.return_value.__enter__.return_value.name = ANY
            get_secrets.return_value = {}
            mock_os.environ = mock_environment.copy()

            # When
            deploy.run()

            # Then
            assert mock_os.environ == mock_environment

    deploy_data = fixed_dictionaries({
        'team': text(alphabet=printable, min_size=2, max_size=20),
        'dev_account_id': text(alphabet=printable, min_size=12, max_size=12),
        'aws_region': text(alphabet=printable, min_size=5, max_size=12),
        'component_name': text(alphabet=printable, min_size=2, max_size=30),
        'environment_name': text(alphabet=printable, min_size=2, max_size=10),
        'version': text(alphabet=printable, min_size=1, max_size=20),
        'ecs_cluster': text(alphabet=ascii_letters, min_size=8, max_size=32),
        'platform_config_file': text(
            alphabet=printable, min_size=10, max_size=30
        ),
    })

    @given(deploy_data)
    def test_terragrunt_gets_all_parameters(self, data):
        # Given
        deploy_config = DeployConfig(
            data['team'],
            data['dev_account_id'],
            data['platform_config_file']
        )
        boto_session = Session(
            'dummy-access-key-id', 'dummy-secret-access-key', 'dummy-token',
            data['aws_region']
        )
        deploy = Deploy(
            boto_session,
            data['component_name'],
            data['environment_name'],
            data['version'],
            data['ecs_cluster'],
            deploy_config
        )
        image_name = '{}.dkr.ecr.{}.amazonaws.com/{}:{}'.format(
            data['dev_account_id'],
            data['aws_region'],
            data['component_name'],
            data['version']
        )

        secret_file_path = '/mock/file/path'

        # When
        with patch(
            'cdflow_commands.plugins.ecs.check_call'
        ) as check_call, patch(
            'cdflow_commands.plugins.ecs.NamedTemporaryFile', autospec=True
        ) as NamedTemporaryFile, patch(
            'cdflow_commands.plugins.ecs.get_secrets'
        ) as get_secrets:
            NamedTemporaryFile.return_value.__enter__.return_value.name = \
                secret_file_path
            get_secrets.return_value = {}

            deploy.run()

            # Then
            args = [
                '-var', 'component={}'.format(data['component_name']),
                '-var', 'env={}'.format(data['environment_name']),
                '-var', 'aws_region={}'.format(data['aws_region']),
                '-var', 'team={}'.format(data['team']),
                '-var', 'image={}'.format(image_name),
                '-var', 'version={}'.format(data['version']),
                '-var', 'ecs_cluster={}'.format(data['ecs_cluster']),
                '-var-file', data['platform_config_file'],
                '-var-file', secret_file_path,
                'infra'
            ]
            check_call.assert_any_call(
                ['terragrunt', 'plan'] + args,
                env=ANY
            )
            check_call.assert_any_call(
                ['terragrunt', 'apply'] + args,
                env=ANY
            )


class TestEnvironmentSpecificConfigAddedToTerraformArgs(unittest.TestCase):

    @given(text(alphabet=ascii_letters, min_size=2, max_size=10))
    def test_environment_specific_config_in_args(self, env_name):

        # Given
        boto_session = Session(
            'dummy-access-key', 'dummy-secreet-access-key',
            'dummy-session-token', 'eu-west-1'
        )
        deploy_config = DeployConfig(
            'dummy-team', 'dummy-account-id', 'dummy-platform-config-file'
        )
        deploy = Deploy(
            boto_session, 'dummy-component', env_name,
            'dummy-version', 'dummy-ecs-cluster', deploy_config
        )

        # When
        with patch(
            'cdflow_commands.plugins.ecs.check_call'
        ) as check_call, patch(
            'cdflow_commands.plugins.ecs.path'
        ) as path, patch(
            'cdflow_commands.plugins.ecs.NamedTemporaryFile', autospec=True
        ) as NamedTemporaryFile, patch(
            'cdflow_commands.plugins.ecs.get_secrets'
        ) as get_secrets:
            NamedTemporaryFile.return_value.__enter__.return_value.name = ANY
            get_secrets.return_value = {}
            path.exists.return_value = True
            deploy.run()
            # Then
            config_file = 'config/{}.json'.format(env_name)
            image_name = '{}.dkr.ecr.{}.amazonaws.com/{}:{}'.format(
                'dummy-account-id', 'eu-west-1',
                'dummy-component', 'dummy-version'
            )
            args = [
                '-var', 'component=dummy-component',
                '-var', 'env={}'.format(env_name),
                '-var', 'aws_region=eu-west-1',
                '-var', 'team=dummy-team',
                '-var', 'image={}'.format(image_name),
                '-var', 'version=dummy-version',
                '-var', 'ecs_cluster=dummy-ecs-cluster',
                '-var-file', 'dummy-platform-config-file',
                '-var-file', ANY,
                '-var-file', config_file,
                'infra'
            ]
            check_call.assert_any_call(
                ['terragrunt', 'plan'] + args,
                env=ANY
            )
            check_call.assert_any_call(
                ['terragrunt', 'apply'] + args,
                env=ANY
            )
            path.exists.assert_any_call(config_file)
