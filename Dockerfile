# FROM python:3.9

# ARG LAMBDA_TASK_ROOT=/var/task

# RUN apt-get update && apt-get upgrade -y

# RUN apt-get install --no-install-recommends --yes wget python3-pip ca-certificates && \
#     wget https://github.com/seqeralabs/tower-cli/releases/download/v0.5/tw-0.5-linux-x86_64 && \
#     chmod +x ./tw-0.5-linux-x86_64 && \
#     mv ./tw-0.5-linux-x86_64 /usr/local/bin/tw && \
#     rm -rf /var/lib/apt/lists/*

# WORKDIR ${LAMBDA_TASK_ROOT}

# # This is an AWS-provided script that allows a container run locally to emulate the AWS Service
# COPY entry_script.sh .
# ADD aws-lambda-rie-x86_64 /usr/local/bin/aws-lambda-rie-x86_64

# COPY requirements.txt .
# RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# COPY app.py "${LAMBDA_TASK_ROOT}"

# ENTRYPOINT [ "./entry_script.sh" ]
# CMD [ "app.handler" ]

# Stage 1: Build
FROM python:3.9-slim AS builder

RUN apt-get update && apt-get upgrade && apt-get install --no-install-recommends --yes python3-pip binutils && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt 
# RUN pwd && ls -al && find / -name '__main__.py' && rm awslambdaric/__main__.py
RUN pwd && ls -al && find / -name '__main__.py' && rm /usr/local/lib/python3.9/site-packages/awslambdaric/__main__.py
COPY app.py .

COPY awslambdaric__main__.py /usr/local/lib/python3.9/site-packages/awslambdaric/__main__.py
COPY lambda_app.py .

# Create a standalone executable
RUN pip install pyinstaller
RUN pyinstaller --onefile lambda_app.py


## Stage: Final Image
FROM debian:bookworm-slim

ARG LAMBDA_TASK_ROOT=/var/task
WORKDIR ${LAMBDA_TASK_ROOT}
ENV PATH="$PATH:${LAMBDA_TASK_ROOT}"

# RUN apt-get update && apt-get upgrade -y && apt-get install --no-install-recommends --yes wget ca-certificates && \
#     wget https://github.com/seqeralabs/tower-cli/releases/download/v0.5/tw-0.5-linux-x86_64 && \
#     chmod +x ./tw-0.5-linux-x86_64 && \
#     mv ./tw-0.5-linux-x86_64 /usr/local/bin/tw && \
#     rm -rf /var/lib/apt/lists/*


# This is an AWS-provided script that allows a container run locally to emulate the AWS Service
COPY --from=builder /app/dist/lambda_app lambda_app
COPY entry_script.sh .
ADD aws-lambda-rie-x86_64 /usr/local/bin/aws-lambda-rie-x86_64

ENTRYPOINT [ "./entry_script.sh" ]
