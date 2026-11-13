-- psql quotes the value as an SQL literal; credentials are read from the environment.
\getenv iv_app_password IV_LOCAL_DB_PASSWORD
CREATE ROLE iv_app LOGIN PASSWORD :'iv_app_password';
CREATE DATABASE industrial_vision OWNER iv_app;
