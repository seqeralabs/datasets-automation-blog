"""
Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""

import os
import sys

import app  # <--- NEW

from . import bootstrap


def main():
    app_root = os.getcwd()
    handler = "app.handler"  # <---- DO NOT CHANGE
    lambda_runtime_api_addr = os.environ["AWS_LAMBDA_RUNTIME_API"]

    bootstrap.run(app_root, handler, lambda_runtime_api_addr)
