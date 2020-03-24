FROM python:3.8.2-alpine3.11


COPY requirements.txt .

RUN \
  pip install -r requirements.txt && \
  rm requirements.txt

COPY yamja-renderer.py /usr/local/bin/yamja-renderer

USER nobody

ENTRYPOINT ["yamja-renderer"]

# [EOF]
