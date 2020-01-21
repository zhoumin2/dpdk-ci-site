# This image is only for development
FROM python:3.6

ENV PYTHONUNBUFFERED 1

RUN apt-get -y update && apt-get -y install \
    libldap2-dev libsasl2-dev curl gnupg python3-coverage

RUN curl -sL https://deb.nodesource.com/setup_12.x | bash -
RUN apt-get -y install nodejs

# Allow pip proxy at build time
ARG PIP_INDEX
ARG PIP_INDEX_URL
ARG PIP_TRUSTED_HOST

COPY requirements ./
RUN pip install -r /local.txt
RUN pip install pre-commit

# Allow npm proxy
ARG NPM_REGISTRY
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry $NPM_REGISTRY; fi

RUN mkdir /workspace

# Set workdir for compose file's manage.py
WORKDIR /workspace/cisite
