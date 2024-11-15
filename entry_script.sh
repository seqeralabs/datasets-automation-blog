#!/bin/sh

# WARNING: THIS WILL NOT WORK if you change the name of `lambda_app.py` and `app.py` in the repo!

# Reference: https://docs.aws.amazon.com/lambda/latest/dg/images-test.html
if [ -z "${AWS_LAMBDA_RUNTIME_API}" ]; then
  echo '---AWS_LAMBDA_RUNTIME_API not found'
  exec /usr/local/bin/aws-lambda-rie-x86_64 lambda_app
else
  echo '+++AWS_LAMBDA_RUNTIME_API found'
  exec lambda_app
fi
