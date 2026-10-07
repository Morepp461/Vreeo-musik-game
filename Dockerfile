FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl unzip git \
    && curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/local/bin:${PATH}" \
    YTDL_POT_PROVIDER_URL="http://127.0.0.1:4416"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN git clone --depth 1 --branch 2.0.1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil-ytdlp-pot-provider
RUN cd /opt/bgutil-ytdlp-pot-provider/server && deno install --allow-scripts=npm:canvas --frozen
COPY bot ./bot
COPY database ./database
CMD ["sh","-c","cd /opt/bgutil-ytdlp-pot-provider/server/node_modules && deno run --allow-env --allow-net --allow-ffi=. --allow-read=. ../src/main.ts & exec python -m bot.main"]
