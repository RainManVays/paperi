# Old-ish Ubuntu base for a low glibc floor (wide runtime compatibility),
# with Python 3.12 added via deadsnakes so the frozen interpreter's minor
# version matches current Ubuntu 24.04 / Linux Mint 22 — required for the
# system python3-bluez .so to be ABI-compatible at runtime (see
# docs/BLUETOOTH_SETUP.md and docs/appimage-packaging-guide.md).
FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common \
        gnupg \
        build-essential \
        curl \
        wget \
        file \
        desktop-file-utils \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
        python3.12 \
        python3.12-venv \
        python3.12-dev \
        python3.12-tk \
        libxcursor1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /repo
