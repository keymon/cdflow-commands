
from subprocess import Popen, PIPE, call
from re import match, search, sub
from os import path, getcwd, environ
import json
import boto3
import botocore

class UserError(Exception):

    """
    User errors that should exit the program and display an error.
    """
    
    pass


class ShellRunner:
    def run(self, command, capture=False):
        if capture:
            cmd = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
            (stdout, stderr) = cmd.communicate()
            stdout = stdout.decode('utf-8')
            stderr = stderr.decode('utf-8')
            return cmd.returncode, stdout, stderr
        else:
            return call(command, shell=True), None, None
        
    def check_run(self, command):
        cmd = Popen(command, shell=True)
        if cmd.wait() != 0:
            raise Exception('non-zero exit status from ' + cmd)     

         
class ServiceJsonLoader():

    """
    Mockable loader for service.json.
    """
    
    def load(self):
        if not path.exists('service.json'):
            raise UserError('service.json not found')
        with open('service.json') as f:
            try:
                metadata = json.loads(f.read())
            except json.decoder.JSONDecodeError as e:
                raise UserError('malformed service.json - ' + str(e))
        return metadata


def get_component_name(arguments, environ, shell_runner):
    """
    Get the component name from the command line option, environment variable or
    from the repo name (path component before ".git" in remote.origin.url).
    """
    arg = arguments.get('--component-name')
    if arg is not None:
        return arg
    env_var = environ.get('COMPONENT_NAME', None)
    if env_var is not None:
        return env_var
    return get_component_name_from_git(shell_runner)

def get_component_name_from_git(shell_runner):
    """
    Get the component name from the git repo name (path component before ".git" in remote.origin.url).
    """
    returncode, stdout, stderr = shell_runner.run('git config remote.origin.url', capture=True)
    if returncode != 0:
        if stdout == '':
            raise UserError(
                'could not get component name from name of remote - no remote returned from "git config remote.origin.url": ' + stderr)
        else:
            raise Exception(
                'git returned non-zero exit status - ' + stderr)
    match = search(r'/([^/.\n]+)(?:\.git)?$', stdout)
    if match is None:
        raise Exception(
            'could not get component name from remote "%s"' % (stdout))
    return match.group(1)
    
def get_default_domain(component_name):
    """
    Returns the default (i.e. by convention) domain name based on the component name.
    """
    for postfix, domain in [('-service', 'mmgapi.net'), ('-subscriber', 'mmgsubscriber.com'), ('-admin', 'mmgadmin.com')]:
        if component_name.endswith(postfix):
            return domain
    return 'mergermarket.it'
    
global_config = None
def get_global_config():
    """
    Returns global config for MMG infrastructure.
    """
    global global_config
    if global_config is None:
        with open(path.join(path.dirname(path.realpath(__file__)), 'global.json')) as f:
            global_config = json.loads(f.read())
    return global_config

def ecr_registry(account_prefix, region):
    return '%s.dkr.ecr.%s.amazonaws.com' % (
        get_global_config()['accountids']['%sdev' % account_prefix],
        region,
    )

def apply_metadata_defaults(metadata, component_name):
    """
    Applies default values to service metadata.
    """
    if 'TEAM' not in metadata:
        raise UserError('TEAM missing from service metadata (service.json)')

    def set_default(k, v):
        if k not in metadata:
            metadata[k] = v

    set_default('REGION', 'eu-west-1')
    set_default('ACCOUNT_PREFIX', 'mmg')

    set_default('TYPE', 'docker')

    # can be explicitly None (null)
    set_default('DOMAIN', get_default_domain(component_name))
    set_default('DNS_NAME', None)
    if metadata['DNS_NAME'] is None and metadata['DOMAIN'] is not None:
        metadata['DNS_NAME'] = sub(r'-(?:service|subscriber|admin)$', '', component_name)

    set_default('ELBTYPE', 'internal')
    set_default('HEALTHCHECK_SUFFIX', '/internal/healthcheck')

    # release specific, but keeping in one place
    set_default('DOCKER_BUILD_DIR', '.')

    set_default('SLUG_BUILDER_DOCKER_OPTS', '')
    
    # deployment specific, but keeping in one place
    set_default('CONFIG_HANDLER', 'toml-inline')
    
    return metadata

def role_session_name():
    if 'JOB_NAME' in environ:
        if match(r'[\w+=,.@/-]{2,64}', environ['JOB_NAME']) is None:
            raise Exception(r'JOB_NAME must match [\w+=,.@/-]{2,64}')
        return sub(r'/', '-', environ['JOB_NAME'])
    elif 'EMAIL' in environ:
        if match(r'[\w+=,.@-]{2,64}', environ['EMAIL']) is None:
            raise Exception(r'EMAIL must match [\w+=,.@-]{2,64}')
        return environ['EMAIL']
    else:
        raise Exception('JOB_NAME or EMAIL environment variable must be set for session name of assumed role')

def assume_role_credentials(region, account_prefix, prod=False):
    account = account_prefix + ('prod' if prod else 'dev')
    print("Assuming role {}".format(account))
    try:
        session = boto3.session.Session(region_name=region)
        credentials = session.client('sts').assume_role(
            RoleArn=('arn:aws:iam::%s:role/admin' % get_global_config()['accountids'][account]),
            RoleSessionName=role_session_name(),
        )['Credentials']
    except botocore.exceptions.NoCredentialsError as e:
        raise UserError('could not connect to AWS mergermarket account: ' + str(e))
    return credentials['AccessKeyId'], credentials['SecretAccessKey'], credentials['SessionToken']

def assume_role(region, account_prefix, prod=False):
    access_key_id, secret_access_key, session_token = assume_role_credentials(region, account_prefix, prod)
    return boto3.session.Session(
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        aws_session_token=session_token,
        region_name=region,
    )

def registry(self):
        """
        Get the ECR repository.
        """
        return ecr_registry(self.metadata['ACCOUNT_PREFIX'], self.metadata['REGION'])

def container_image_name(registry, component_name, version):
    if version is None:
        image = component_name + ':dev'
    else:
        image = '%s/%s:%s' % (registry, component_name, version)

    return image
