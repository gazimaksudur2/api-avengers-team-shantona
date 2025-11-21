#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE donations_db;
    CREATE DATABASE payments_db;
    CREATE DATABASE notifications_db;
EOSQL

