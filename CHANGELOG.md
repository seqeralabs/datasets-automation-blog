# CHANGELOG

## NOTE
The material in this repo is getting old. 

For consistency purposes, the original package versions have been maintained (_i.e. Python3.9 and TW CLI 0.5_). This approach required the  Dockerfile to be rewritten from its original state in order to cleanly/easily retain access to a Python3.9 runtime. I recommend using git history / blame on the Dockerfile to compare the original state vs updated state.

Anyone implementing now (_circa early November 2024_) should - at the very least - consider using a newer version of TW CLI and assess whether pinned Python packages in `requirements.txt` should be bumped.


## CHANGES
- Nov 2, 2024: Modified `Dockerfile` and `entry_script.sh` to implement a true fix for the problem that the May 8/24 fix attempted to solve. [PR #7](https://github.com/seqeralabs/datasets-automation-blog/pull/7)

- Nov 2, 2024: Modified `s3key` string-splitting logic to accommodate more complex S3 prefixes. [PR #6](https://github.com/seqeralabs/datasets-automation-blog/pull/6)

- May 8, 2024: [Dockerfile modified](https://github.com/seqeralabs/datasets-automation-blog/pull/2) to fix `apt-get install python3.9` error. **NOTE:** This change introduced a catastrophic bug that exhibited at runtime. Please ensure you update your code to pick up new fixes.
