#!/bin/sh

# Reference: https://docs.aws.amazon.com/lambda/latest/dg/images-test.html
if [ -z "${AWS_LAMBDA_RUNTIME_API}" ]; then
  exec /usr/local/bin/aws-lambda-rie-x86_64 /usr/local/bin/python -m awslambdaric "$@"
else
  exec /usr/local/bin/python -m awslambdaric "$@"
fi
