FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
ENV SQLGLOT_ROOT=/opt/sqlglot COVERAGE_MAP=/tmp/coverage.json PYTHONPATH=/opt/sqlglot:/app SKIP_INTEGRATION=0
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r /app/requirements.lock
RUN mkdir /opt/sqlglot && cd /opt/sqlglot && git init -q && git remote add origin https://github.com/tobymao/sqlglot.git && git fetch -q --depth=1 origin eb11aec4be8cb2122afe713a4816662c3f0fb2fa && git checkout -q FETCH_HEAD
COPY selector.py coverage_plugin.py build_maps.py /app/
RUN cd /opt/sqlglot && pytest -q -p coverage_plugin tests >/tmp/pytest.log 2>&1; test -s /tmp/coverage.json
RUN python /app/build_maps.py && chmod 644 /app/maps.json && rm -rf /opt/sqlglot /tmp/coverage.json /tmp/pytest.log
CMD ["python", "/app/selector.py"]
