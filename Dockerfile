FROM python:3.9-alpine

WORKDIR "/yepcord"

RUN apk update && apk add gcc libc-dev libmagic git bash
RUN python -m pip install --upgrade pip && pip install --upgrade wheel setuptools
COPY requirements.txt requirements.txt
COPY requirements-s3.txt requirements-s3.txt
COPY requirements-ftp.txt requirements-ftp.txt

RUN pip install -r requirements.txt
RUN pip install -r requirements-s3.txt
RUN pip install -r requirements-ftp.txt

COPY . .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]