import base64
import datetime
import json
import logging
import pathlib
import os
import subprocess

import boto3
# This library included as an example for how to get Boto3 autocomplete
# in VSCode. Could be removed when creating your Production image for minor
# storage saving.
from mypy_boto3_secretsmanager import SecretsManagerClient


# Create logger. Set to DEBUG by default for testing. Change level via SSM Parameter.
logger = logging.getLogger('lambda_tutorial')
logger.setLevel(logging.DEBUG)


# Custom error defintion to use when we need to stop mid-function and NOT retry.
# The `handler` function exception block looks for this error and returns, meaning native Lambda 
# retry logic won't execute.
class CeaseEventProcessing(Exception):
    pass


def generate_session(execution_role=None):
    '''
        The Lambda function needs to be able to access other AWS service like Secrets Manager
        and S3 when being tested locally (and won't have access to its execution role). Boto3 checks multiple 
        places for credentials 
        (see: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).

        When running inside the Lambda platform, the function will inherit its credentials from
        environment variables generated when the function assumes its execution role. 

        When running locally, I supply credentials to the container by mapping my already-configured
        AWS CLI creds into the container at runtime (`-v ~/.aws:/root/.aws:ro`). The default profile 
        is a user with Admin privileges, however, so we want to emulate the permission set the Production
        function will have, so I'll immediately assume the execution role when testing locally.

        When the function is first invoked, check for the presence of the mounted credentials file. 
        If the file is present, we know its a local run. If not, the function is being executed in AWS. 
    '''
    # Check if the .aws file is mounted into the container.
    mounted_credentials_file = pathlib.Path('/root/.aws/credentials')
    credentials_present = False
    try:
        credentials_present = mounted_credentials_file.is_file()
        logger.debug('Found credentials file. Running locally.')
    except PermissionError:
        logger.debug('Did not find credentials file. Running remotely in Lambda.')

    # Create Session
    session = boto3.Session()

    if credentials_present:
        # Assume the execution Role
        iam_client = session.client('iam')
        sts_client = session.client('sts')

        try:
            response = iam_client.get_role(RoleName=execution_role)

            execution_role_arn = response['Role']['Arn']
            assumed_role_object = sts_client.assume_role(
                RoleArn=execution_role_arn, 
                RoleSessionName='LocalAssumingLambdaRole'
            )

        except Exception as e:
            # Transaction may have failed due to networking. Retryable.
            log_error_and_raise_exception(
                errorstring=f"Could not find execution role: {execution_role}.", 
                e=e,
                retry_transaction=True
            )

        # Extract the temporary credentials for the execution role.
        # Generate a new session based on the execution Role.
        try:
            credentials = assumed_role_object['Credentials']

            session = boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken']
            )

        except KeyError as e:
            # Transaction may have failed due to networking. Retryable.
            log_error_and_raise_exception(
                errorstring=f"Could not create new assumed role session.", 
                e=e,
                retry_transaction=True
            )

    return session


def get_parameters(session=None, params_to_retrieve=None):
    '''
        Pipeline-related values like workspace ID and pipeline name need to be available so that the
        tower cli creates a Dataset in the right Workspace and invokes the correct pipeline.
        Externalize these in AWS SSM so they can be changed without requiring modification of the
        underlying image or Lambda function code.

        Example: {'Parameter': 
            {'Name': '/lambda_tutorial/workspace_id', 
            'Type': 'String', 
            'Value': '34830707738561', 
            'Version': 3, 
            ...
    '''
    tw_params = {}
    ssm_client = session.client('ssm')

    for param in params_to_retrieve:
        try:
            # My SSM keys aren't KMS encrypted, so we can treat them as strings.
            response = ssm_client.get_parameter(Name=param, WithDecryption=False)
            tw_params[param] = response['Parameter']['Value']
            logger.debug(tw_params[param])

            # Update logging_level based on logging_level key.
            if param == '/lambda_tutorial/logging_level':
                desired_level = tw_params[param]
                if desired_level.upper() != "DEBUG":
                    update_logging_level(desired_level=desired_level)

            logger.debug(response)
            
        except ssm_client.exceptions.ParameterNotFound as e:
            # Transaction may have failed due to networking. Retryable.
            log_error_and_raise_exception(
                errorstring=f"Parameter {param} not found",
                e=e,
                retry_transaction=True
            )

    return tw_params


def get_secrets(session=None):
    '''
        Need to protect the Tower PAT more securely. Could use SSM with KMS, but I'm using Secrets Manager
        for a simpler implementation.

        Example: {'tower_PAT': 
            {'ARN': 'arn:aws:secretsmanager:YOUR_REGION:YOUR_ACCOUNT:secret:lambda_tutorial/tower_PAT-Abcdef', 
            'Name': 'lambda_tutorial/tower_PAT', 
            'SecretString': 'eyJ0.....', 
           ...
    '''
    tw_secrets = {}
    secret_name = "lambda_tutorial/tower_PAT"
    secrets_client: SecretsManagerClient = session.client('secretsmanager')

    try:
        get_secret_value_response = secrets_client.get_secret_value(
            SecretId=secret_name
        )
    # Modified exception logic provided in SecretsManager console
    except secrets_client.exceptions.DecryptionFailure as e:
        # Secrets Manager can't decrypt the protected secret text using the provided KMS key. Do not retry.
        log_error_and_raise_exception(
            errorstring="KMS decryption error.", e=e, retry_transaction=False
        )
    except secrets_client.exceptions.InternalServiceError as e:
        # Generic error. Retry.
        log_error_and_raise_exception(
            errorstring="An unspecified error occured on the server.", e=e, retry_transaction=True
        )
    except secrets_client.exceptions.InvalidParameterException as e:
        # Invalid Parameter value. Do not retry.
        log_error_and_raise_exception(
            errorstring="Invalid parameter name provided.", e=e, retry_transaction=False
        )
    except secrets_client.exceptions.InvalidRequestException as e:
        # Invalid parameter value for current state of resource. Retry.
        log_error_and_raise_exception(
            errorstring="Invalid parameter name provided.", e=e, retry_transaction=True
        )
    except secrets_client.exceptions.ResourceNotFoundException as e:
        # Transaction may have failed due to networking. Retryable.
        log_error_and_raise_exception(
            errorstring="Tower_PAT secret not found", e=e, retry_transaction=True
        )
    else:
        # Decrypts secret using the associated KMS key.
        # Depending on whether the secret is a string or binary, one of these fields will be populated.
        if 'SecretString' in get_secret_value_response:
            tw_secrets['tower_PAT'] = get_secret_value_response['SecretString']
        else:
            tw_secrets['tower_PAT'] = base64.b64decode(get_secret_value_response['SecretBinary'])

    return tw_secrets


def set_environment_variables(tw_params=None, tw_secrets=None):
    '''
        Define TOWER_ACCESS_TOKEN and TOWER_API_ENDPOINT environment variables for use
        by the tw cli. 
        Set this before running tw transactions.
    '''
    os.environ['TOWER_ACCESS_TOKEN'] = tw_secrets['tower_PAT']
    os.environ['TOWER_API_ENDPOINT'] = tw_params['/lambda_tutorial/tower_api_endpoint']


def check_if_event_in_scope(event=None, tw_params=None):
    '''
        Check if event is for a file that must be convert to a Dataset.
        Notes:
            1) Prefix is not specifically defined in the event so it needs to be defined.
            2) Boto3 S3 client list_objects requires the Prefix parameter to have a '/' at the end
                so we add this back in since the split function removes it
        Example of object key:
            "lambda_tutorial/samplesheet_full.csv"
    '''
    # Check if event should be processed or ignored. Cease processing if:
    #   1) Notification isn't from designated prefix.
    #   2) Notification doesn't match file type trigger.
    event_key = event['Records'][0]['s3']['object']['key']
    filetype = event_key.rsplit('.', 1)[1]

    if not event_key.startswith(tw_params['/lambda_tutorial/s3_root_prefix']):
        # Event is out of scope and should not be retried.
        log_error_and_raise_exception(
            errorstring=f"Event key: {event_key} does not match designated prefix. Cease processing.",
            e=None,
            retry_transaction=False
        )

    if filetype not in tw_params['/lambda_tutorial/samplesheet_file_types'].split(','):
        # Event is out of scope and should not be retried.
        log_error_and_raise_exception(
            errorstring=f"Event key: {event_key} not a trigger file type. Cease processing.",
            e=None,
            retry_transaction=False
        )


def download_samplesheet(session=None, event=None):
    '''
        Download the S3 file to a local directory.
        Return two paths: 
            1) Absolute path to the local file; 
            2) Filename without extension (to use as the dataset name)
    '''
    s3_client = session.client('s3')

    try:
        s3bucket = event['Records'][0]['s3']['bucket']['name']
        s3key = event['Records'][0]['s3']['object']['key']
        # Example of key: "lambda_tutorial/complete.txt"
        samplesheet_filename = s3key.rsplit('/')[1]
        dataset_name = samplesheet_filename.split('.')[0]

    except Exception as e:
        # Failure to extract and parse data will not change if retried. Do not retry.
        log_error_and_raise_exception(
            errorstring=f"Failed to prepare file details for download", 
            e=e,
            retry_transaction=False
        )

    try:
        # Make local directory and download file:
        p = pathlib.Path('/tmp/s3files/')
        p.mkdir(parents=True, exist_ok=True)

        p_posix = p.as_posix()
        local_samplesheet = f"{p_posix}/{samplesheet_filename}"

        s3_client.download_file(s3bucket, s3key, local_samplesheet)
        logger.debug(f"File downloaded locally: {os.listdir(p_posix)}")

    except Exception as e:
        # Transaction may have failed due to networking. Retryable.
        log_error_and_raise_exception(
            errorstring="Failed to create temporary folder or download S3 file.", 
            e=e,
            retry_transaction=True
        )

    return local_samplesheet, dataset_name


def create_tower_dataset(local_samplesheet=None, dataset_name=None, event=None, tw_params=None):
    '''
        Use the tw cli to create a dataset in Tower.
        Assumption: Header is always present.
    '''
    s3bucket = event['Records'][0]['s3']['bucket']['name']
    s3key = event['Records'][0]['s3']['object']['key']
    s3source = f"s3://{s3bucket}/{s3key}"

    workspace_id = tw_params['/lambda_tutorial/workspace_id']
    description = f"Generated by Lambda {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} from {s3source}"

    # Python subprocess module works best with command split into array. 
    # Using split(' ') mostly works but fails on multi-word description. Adding description and filepath after split.
    # Use the JSON output option to make it easier to work with Tower's response.
    command = f"tw -o json datasets add --workspace={workspace_id} --name={dataset_name} --header"
    command = command.split(' ')
    # DONT put spaces before hyphens or else `tw` throws error `unmatched argument`
    command.append(f"--description='{description}'")
    command.append(f"{local_samplesheet}")  
    logger.debug(f"command is: {command}")

    # Transaction could fail due to networking. Retryable.
    result = invoke_tw_cli(
        command=command, 
        errorstring=f"Failed to create dataset for file {s3source}",
        retry_transaction=True
    )
    logger.debug(f"Dataset creation confirmation is: {result}")

    # Extract dataset ID from positive response
    try:
        datasetid = result['datasetId']
        logger.debug(f"Datasetid is: {datasetid}")
    except Exception as e:
        # Failure to extract and parse data will not change if retried. Do not retry.
        log_error_and_raise_exception(
            errorstring="Failed extract dataset ID.", 
            e=e,
            retry_transaction=False
        )

    return datasetid


def launch_tower_pipeline(datasetid=None, tw_params=None):
    '''
        With the datasetid in hand, launch a pipeline. To do so:
            1) Get the URL for the newly-created samplesheet.
            2) Specify the URL as the input source parameter.
            3) Invoke the target pipeline passing the parameter file with the defined input source.
    '''
    # Extract parameters for inclusion in tw commands
    workspace_id = tw_params['/lambda_tutorial/workspace_id']
    target_pipeline_name = tw_params['/lambda_tutorial/target_pipeline_name']

    # Generate command for dataset URL retrieval (required for subsequent pipeline launch comand)
    command = f"tw -o json datasets url --workspace={workspace_id} --id={datasetid}"
    command = command.split(' ')
    logger.debug(f"command is: {command}")

    # Transaction could fail due to networking. Retryable.
    result = invoke_tw_cli(
        command=command, 
        errorstring=f"Could not retrieve URL for dataset {datasetid} from workspace {workspace_id}",
        retry_transaction=True
    )
    logger.debug(f"Dataset URL is: {result}")

    # Extract dataset URL from response and add to parameters file as input source.
    try:
        dataset_url = result['datasetUrl']
        logger.debug(f"Dataset URL is: {dataset_url}")

        # Create parameters file (JSON) to pass to pipeline (with dataset specified as input source)
        input_params = {}
        input_params['input'] = dataset_url

        # Make local directory and write file:
        p = pathlib.Path('/tmp/tower_input_files/')
        p.mkdir(parents=True, exist_ok=True)

        p_posix = p.as_posix()
        filepath = f"{p_posix}/{datasetid}.json"
        with open(filepath, "w") as f:
            json.dump(input_params, f)

    except Exception as e:
        # Failure to extract and parse data will not change if retried. Do not retry.
        log_error_and_raise_exception(
            errorstring=f"Failed to create json file for pipeline input.", 
            e=e,
            retry_transaction=False
        )

    # Invoke pipeline (passing parameters file)
    command = f"tw -o json launch --workspace={workspace_id} --params-file={filepath} {target_pipeline_name}"
    command = command.split(' ')
    logger.debug(f"command is: {command}")

    result = invoke_tw_cli(
        # This transaction may have failed due to networking but - based on the current logic - it cannot be 
        # retried. If we rerun the whole function, and error will be thrown earlier when the Lambda function tries
        # to create a Dataset in Tower which already exists.
        # This function can become retryable once the Dataset creation code is made more robust.
        command=command, 
        errorstring=f"Could not invoke target pipeline.",
        retry_transaction=False
    )


def invoke_tw_cli(command=None, errorstring=None, retry_transaction=None):
    '''
        Generic function to invoke subprocess calls to tw cli.
        Invoking functions must pass:
            1) Tokenized command (to facilitate use of python `subprocess` module),
            2) Error string for logging purposes in event of failure.
        NOTE: Function must convert the string-represented JSON returned  by tw to a dictionary for use by Python.
    '''
    try:
        result = subprocess.run(command, capture_output=True)
    except Exception as e:
        # Depending on command being invoked, may be retryable. Use value passed in from source to determine.
        log_error_and_raise_exception(
            errorstring=errorstring,
            e=e,
            retry_transaction=retry_transaction
        )

     # Log output of tw calls (for troubleshooting purposes)
    logger.debug(f"Return code from tw was: {result.returncode}")
    logger.debug(f"Stdout from tw was: {result.stdout}")
    logger.debug(f"Stderr from tw was: {result.stderr}")

    if result.returncode != 0:
        # Indicates something is wrong with the request itself. Do not retry as the outcome will not change.
        log_error_and_raise_exception(
            errorstring=f"TW returned non-zero code:\nCode: {result.returncode}\nOriginal Error: {result.stderr}",
            e=None,
            retry_transaction=False
        )
 
    return json.loads(result.stdout)


def log_error_and_raise_exception(errorstring=None, e=None, retry_transaction=True):
    '''
        This function is used to capture the reasons for why the Lambda code ceased prematurely.
        Can be triggered for two reasons:
            1) Actual programming exception which was not properly handled.
            2) Deliberate invocation when evaluation logic determines the event is OOS and should be ignored.

        Lambda retry logic is powerful and we want to leverage it for handling event like networking hiccups that could 
        cause a transaction to fail, but we don't want to retry events that we failed on purpose (e.g. because
        the file type was wrong and indicated the file was not a sample sheet).
        
        The handler function has been configured to return when it detects a CeaseEventProcessing exception
        (ending the event processing cleanly and not triggering a Lambda retry), but will return a generic 
        Exception in any other case, which will cause Lambda to retry the event.
    '''
    logger.debug(f"[EXCEPTION]: {errorstring}")
    if e:
        logger.debug(f"{e}")
    
    if retry_transaction:
        raise Exception('Transaction failed but may succeed on retry. Retrying.')
    else:
        raise CeaseEventProcessing('Transaction ceased deliberately. Do not retry.')
        

def update_logging_level(desired_level=None):
    '''
        Change logger level without requiring deployment of new image.
    '''
    log_levels = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL']
    desired_level = desired_level.upper()

    if desired_level in log_levels:
        logger.setLevel(desired_level)
        logger.warning(f"Modified logging level to {desired_level}")
    else:
        # Create logger alert and stick with default DEBUG
        logger.error(f"SSM parameter 'lambda_tutorial/logging_level' value {desired_level} is not a valid logging level. Continuing with DEBUG.")


def handler(event, context):
    '''
        The first function that will be invoked when Lambda is activated.
    '''
    try:
        # Hard-coded value to simplify the generation of a session. 
        # Could be externalized but would require more complicated logic to retrieve externalized value (when
        # testing locally). 
        execution_role = 'lambda_tutorial'
        session = generate_session(execution_role=execution_role)
        logger.debug(f"Session client is: {session.client('sts').get_caller_identity()}")

        # Get parameters from SSM
        # Update function logging level (if necessary) when `logging_level` parameter is retrieved.
        # NOTE:
        #   Keynames are odd for a Python dictionary, but it works and aligns with required AWS set-up commands.
        #   Keep logging_level as first entry to control logging behaviour of other values when retrieved.
        params_to_retrieve = [
            '/lambda_tutorial/logging_level',
            '/lambda_tutorial/workspace_id',
            '/lambda_tutorial/s3_root_prefix',
            '/lambda_tutorial/samplesheet_file_types',
            '/lambda_tutorial/target_pipeline_name',
            "/lambda_tutorial/tower_api_endpoint"
        ]
        tw_params = get_parameters(session=session, params_to_retrieve=params_to_retrieve)
        logger.debug(f"Parameters are: {tw_params}")

        # Check event to see if newly-arrived file needs to be processed. If yes, continue.
        check_if_event_in_scope(event=event, tw_params=tw_params)

        # Get Secrets from AWS Secrets Manager & set as environment variables
        tw_secrets = get_secrets(session=session)
        logger.debug(f"Secrets are: {tw_secrets}")
        set_environment_variables(tw_params=tw_params, tw_secrets=tw_secrets)

        # Download the file from S3 and push to Tower as a new dataset
        local_samplesheet, dataset_name = download_samplesheet(session=session, event=event)

        datasetid = create_tower_dataset(
            local_samplesheet=local_samplesheet, 
            dataset_name=dataset_name, 
            event=event, 
            tw_params=tw_params
        )

        # Invoke a pre-existing pipeline with the newly-created dataset
        launch_tower_pipeline(datasetid=datasetid, tw_params=tw_params)
        return "Pipeline completed successfully."

    except CeaseEventProcessing as e:
        # Event was terminated on purpose. Do not retry.
        return "Pipeline was terminated early."
