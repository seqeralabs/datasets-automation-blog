# CHANGELOG

- Nov 2, 2024: Modified `s3key` string-splitting logic to accommodate more complex S3 prefixes. [PR #6](https://github.com/seqeralabs/datasets-automation-blog/pull/6)

- May 8, 2024: [Dockerfile modified](https://github.com/seqeralabs/datasets-automation-blog/pull/2) to fix `apt-get install python3.9` error. **NOTE:** This change introduced a catastrophic bug that exhibited at runtime. Please ensure you update your code to pick up new fixes.
