FROM node:20-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash build-essential ca-certificates curl git \
        jq less procps python3 python3-pip python3-venv \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash botuser

RUN npm install -g @anthropic-ai/claude-code

COPY requirements.txt /workspace/
RUN pip install --no-cache-dir -r /workspace/requirements.txt

COPY bot/ /workspace/bot/
COPY alembic/ /workspace/alembic/
COPY alembic.ini /workspace/alembic.ini
COPY sandbox/ /workspace/sandbox/

RUN chown -R botuser:botuser /workspace

USER botuser
ENV HOME=/home/botuser

CMD ["python", "-m", "bot.main"]
