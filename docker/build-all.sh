#!/bin/bash

variants=(pubsub base http gateway cdn) # add remote_auth

for variant in "${variants[@]}"; do
    docker build -f "Dockerfile.${variant}" -t "yepcord/${variant}:latest" .
done