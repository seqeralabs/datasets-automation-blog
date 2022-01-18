#!/bin/sh

# Reference: https://docs.aws.amazon.com/lambda/latest/dg/images-test.html
if [ -z "${AWS_LAMBDA_RUNTIME_API}" ]; then
  exec /usr/local/bin/aws-lambda-rie-x86_64 /usr/bin/python3 -m awslambdaric "$@"
else
  exec /usr/bin/python3 -m awslambdaric "$@"
fi
