FROM python:3.12.1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /project
COPY . /project

RUN uv sync

ENV PYTHONPATH=./src
CMD ["uv", "run", "zulip-botserver", "--config-file=./botserverrc", "--hostname=0.0.0.0"]
