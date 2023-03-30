#!/bin/bash

variants=(pubsub base api gateway cdn) # add remote_auth

for variant in "${variants[@]}"; do
    docker build -f "docker/Dockerfile.${variant}" -t "yepcord/${variant}:latest" .
done