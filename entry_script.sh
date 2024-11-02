#!/bin/sh

# Reference: https://docs.aws.amazon.com/lambda/latest/dg/images-test.html
if [ -z "${AWS_LAMBDA_RUNTIME_API}" ]; then
  echo '---AWS_LAMBDA_RUNTIME_API not found'
  exec /usr/local/bin/aws-lambda-rie-x86_64 python3 -m awslambdaric "$@"
else
  echo '+++AWS_LAMBDA_RUNTIME_API found'
  exec python3 -m awslambdaric "$@"
fi
