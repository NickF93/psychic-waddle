# Preserve the vendor application and dependency artifacts on its supported ABI.
FROM certbot/certbot:v5.8.0@sha256:f70ad0adbb7e117f0fe42a63c553f28ea451edabc0148757b6efcd9735acaa20 AS vendor
FROM python:3.14.10-alpine3.23@sha256:26d722783e1c79fe2fc18959c491eee46d716c0c7af07ebc541c1553cde7747c

RUN apk add --no-cache libffi libssl3 openssl ca-certificates binutils
COPY --from=vendor /opt/certbot /opt/certbot
COPY --from=vendor /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=vendor /usr/local/bin/certbot /usr/local/bin/certbot
COPY installer.lock requirements.lock /tmp/constraints/
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/constraints/installer.lock \
    && python -m pip install --no-cache-dir --constraint /tmp/constraints/requirements.lock certifi \
    && python -m pip check \
    && certbot --version

WORKDIR /opt/certbot
ENTRYPOINT ["certbot"]
EXPOSE 80 443
VOLUME /etc/letsencrypt /var/lib/letsencrypt
