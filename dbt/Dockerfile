# dbt-mysql (adaptador da comunidade) só suporta dbt-core 1.7.x, por isso o pino.
FROM python:3.11-slim
RUN pip install --no-cache-dir "dbt-core~=1.7.0" "dbt-mysql==1.7.0"
WORKDIR /usr/app
ENV DBT_PROFILES_DIR=/usr/app
ENTRYPOINT ["dbt"]
CMD ["build"]
