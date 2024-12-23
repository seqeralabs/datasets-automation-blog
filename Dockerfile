FROM python:3.9

ARG LAMBDA_TASK_ROOT=/var/task

RUN apt-get update && apt-get upgrade -y

RUN apt-get install --no-install-recommends --yes wget python3-pip ca-certificates && \
    wget https://github.com/seqeralabs/tower-cli/releases/download/v0.5/tw-0.5-linux-x86_64 && \
    chmod +x ./tw-0.5-linux-x86_64 && \
    mv ./tw-0.5-linux-x86_64 /usr/local/bin/tw && \
    rm -rf /var/lib/apt/lists/*

WORKDIR ${LAMBDA_TASK_ROOT}

# This is an AWS-provided script that allows a container run locally to emulate the AWS Service
COPY entry_script.sh .
ADD aws-lambda-rie-x86_64 /usr/local/bin/aws-lambda-rie-x86_64

COPY requirements.txt .
RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

COPY app.py "${LAMBDA_TASK_ROOT}"

ENTRYPOINT [ "./entry_script.sh" ]
CMD [ "app.handler" ]
