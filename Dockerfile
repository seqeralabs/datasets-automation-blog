# Stage 1: Build
FROM python:3.9-slim AS builder

WORKDIR /app

# Needed to generate pyinstaller executable
RUN apt-get update && apt-get upgrade && apt-get install --no-install-recommends --yes \
    python3-pip binutils 
    # && \ rm -rf /var/lib/apt/lists/*

# TW CLI
RUN apt-get install --no-install-recommends --yes \
    wget ca-certificates && \
    wget https://github.com/seqeralabs/tower-cli/releases/download/v0.5/tw-0.5-linux-x86_64 && \
    chmod +x ./tw-0.5-linux-x86_64 && \
    mv ./tw-0.5-linux-x86_64 /usr/local/bin/tw 
    # && \ rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Need to delete the default awslambdaric/__main__.py so we can include app in the single executable.
RUN pip3 install --no-cache-dir -r requirements.txt 
# Test to find the awslambdaric __main__.py file
# RUN pwd && ls -al && find / -name '__main__.py'
RUN rm /usr/local/lib/python3.9/site-packages/awslambdaric/__main__.py

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

RUN apt-get update && apt-get install --no-install-recommends --yes ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/dist/lambda_app lambda_app
COPY --from=builder /usr/local/bin/tw /usr/local/bin/tw
COPY entry_script.sh .
ADD aws-lambda-rie-x86_64 /usr/local/bin/aws-lambda-rie-x86_64

ENTRYPOINT [ "./entry_script.sh" ]
