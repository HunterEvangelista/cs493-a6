#!/bin/bash
docker buildx build --platform linux/amd64 \
  -t us-west1-docker.pkg.dev/evangelh493a3/a5/cs493-a5:latest \
  --push .
