# datasets-automation-blog
Repository for the code and configuration files referenced in the [Workflow Automation for Nextflow Tower Pipelines](https://seqera.io/blog/workflow-automation/) blog post.

The material provided can be built as an [AWS Lambda-compatible container image](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html) which can also be run on your local machine.


# Quickstart

To run this code on your local machine, do the following: 

1. Clone the repository.

    `$ git clone https://github.com/seqeralabs/datasets-automation-blog.git`

1. Instally [Python 3.9](https://www.python.org/downloads/).

1. Install [`docker`](https://docs.docker.com/get-docker/).

1. Install the [`aws cli`](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).

1. Configure the [`aws cli`](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html).

1. Build the Docker image.

    `$ docker build --tag lambda_tutorial:v1.0 .`

1. Run the container.

    `$ docker run --rm -it -v ~/.aws:/root/.aws:ro -p 9000:8080 lambda_tutorial:v1.0`

1. Send a transaction to the container.

    `$ curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d @PATH_TO_YOUR_JSON_TEST_EVENT`

**NOTE:** Transactions will receive error messages until you add the necessary configuration items to your AWS Account (_see below_).


# Required Configuration

The provided code relies on the presence of specific artefacts in your AWS Account and Tower instance.

Please see the [related blog](https://seqera.io/blog/workflow-automation/#prepare-supporting-aws-services) for step-by-step instructions to create the following:

1. AWS
    1. S3 Bucket
    1. IAM Role
        * `lambda_tutorial`
    1. Secrets Manager
        * `lambda_tutorial/tower_PAT`
    1. Systems Manager Parameter Store
        * `/lambda_tutorial/tower_api_endpoint`
        * `/lambda_tutorial//lambda_tutorial/workspace_id`
        * `/lambda_tutorial/target_pipeline_name`
        * `/lambda_tutorial/s3_root_prefix`
        * `/lambda_tutorial/samplesheet_file_types`
        * `/lambda_tutorial/logging_level`
    1. ECR
        * `lambda_tutorial`

2. Nextflow Tower
    1. Personal Access Token


# Deploying to AWS Lambda

To deploy the code to the AWS Lambda Service, please see the [related blog](https://seqera.io/blog/workflow-automation/#create-lambda-function-code-and-container) for step-by-step instructions.

**NOTE:** Do not deploy the image until you have created a local container and created all necessary configuration keys. 


# Folder Structure

The code is organized as follows:

```bash
$ tree
.
├── Dockerfile
├── LICENSE
├── README.md
├── app.py
├── aws-lambda-rie-x86_64
├── datafiles
│   └── samplesheet_full.csv
├── entry_script.sh
├── iam
│   ├── lambda_tutorial_all_permissions.json
│   └── trust_policy.json
├── requirements.txt
└── testing
    ├── test_event_bad_file.json
    ├── test_event_bad_prefix.json
    └── test_event_good.json
```

## Salient features

- The `iam` folder contains the policies you can attach to your AWS IAM Role.

- The `datafiles` folder contains an example sample sheet for the [https://github.com/nf-core/rnaseq](https://github.com/nf-core/rnaseq) pipeline (_the pipeline used during the creation of this material_).

- The `testing` folder contains sample S3 Put notification events that the AWS Lambda Service receives from S3. This can be used when testing locally and/or when testing in the Lambda Service.

- The `aws-lambda-rie-x86_64` and `entry_script.sh` files are used to allow your container to [emulate AWS Lambda](https://docs.aws.amazon.com/lambda/latest/dg/images-test.html) while testing locally.

- The `app.py` file is the Python 3.9 code that will be executed by your Lambda function.<br>

    While most parameters are externalized to supporting AWS Services, three values were hardcoded for ease of development. If you choose to use different names for your configuration items than directed, please ensure that you have updated them in the code as well.

    - `execution_role`<br> 
        The Role used by AWS Lambda to interact with other AWS Services. Set to _lambda_tutorial_.

    - `params_to_retrieve`<br>
        An array populated with the AWS Systems Manager Parameter Store parameters. 

    - `secret_name`<br>
        The AWS Secrets Manager key containing the value of your Tower PAT.


# Caveat

This code was written to demonstrate the art of the possible for clients of Nextflow Tower. It has not yet been optimized for maximum efficiency nor to minimize unnecessary retries. 

Given that AWS Lambda [charges](https://aws.amazon.com/lambda/pricing/) for each MB of RAM on a per 1ms basis, and resulting pipeline invocations will incur charges with your batch computing provider, individuals are advised to conduct further testing and refinements before deployment to Production so as to minimize the risk of unexpected billing. 

