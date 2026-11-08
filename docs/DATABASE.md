# Database (PostgreSQL + Alembic)

Since task Z3 the application uses **PostgreSQL only**; SQLite is no longer supported. The schema is managed by
**Alembic** (`backend/alembic/`): the API upgrades the database to the newest revision when it starts.

## Settings

| Variable | Used by | Example |
|---|---|---|
| `DATABASE_URL` | the application | `postgresql+psycopg://tutor@127.0.0.1:5432/tutor` |
| `PGPASSWORD` | the application (password of `DATABASE_URL`) | in `.env` only |
| `POSTGRES_PASSWORD` | the `db` service of `docker-compose.yml` | same value as `PGPASSWORD` |
| `TEST_DATABASE_URL` | tests and evaluation harnesses | `postgresql+psycopg://tutor@127.0.0.1:5432/tutor` |

The password is never part of a URL: it is passed to the driver from `PGPASSWORD`. `setup_local.py` writes a
random password into `.env` for you. Never commit `.env`.

## Running

- **Whole system**: `docker compose up --build` starts `db` (PostgreSQL 16, data in the `db-data` volume),
  `api` and `web`. `POSTGRES_PASSWORD` must be set in `.env`.
- **Backend on this machine**: start only the database with `docker compose up -d db`; `DATABASE_URL` points at
  `127.0.0.1:5432`. Any other PostgreSQL 14+ server works too.

## Tests and evaluations

`TEST_DATABASE_URL` points at a server where the account may create databases (the `tutor` user of the `db`
service can). Each test run creates its own database `tutor_test_<random>` with the current schema, empties the
tables after every test and drops the database at the end (`backend/app/storage/testing.py`); the evaluation
harnesses (E2, E3, E4) do the same. Nothing touches the application database. CI runs a PostgreSQL service.

## Course catalog and the demo course (task Z4)

Courses, modules, KCs, prerequisites, check items and misconceptions live in the database (`app/catalog`).
On first start an empty database gets the course **General Medical Knowledge** (`MED 0000`), imported from
`content/topics/` with one module per topic. Items and misconceptions without `reviewed_by` in the YAML are
imported as **draft**: students never see them until an instructor publishes them (status `active`).
`CONTENT__SEED_STATUS=active` imports them as published instead; use it only for demos with fictional
students, on a new database (it has no effect once the course exists).

`content.serve_unreviewed` no longer exists; an old `.env` that sets `CONTENT__SERVE_UNREVIEWED` stops the
app with a message saying what to do.

## Moving a v3 installation

```bash
python scripts/migrate_v3.py --source data/app.db
```

copies accounts, learner data, logs and conversation turns from the v3 SQLite file into a new, empty
PostgreSQL database and creates the demo course (course-structure.md section 11). Login sessions are not
copied. Materials and the index follow once the document scanner (Z11) exists.

## Changing the schema

1. Change the models in `backend/app/storage/models.py`.
2. From `backend/`, with `DATABASE_URL` pointing at a database that is at the current revision:

   ```bash
   python -m alembic revision --autogenerate -m "what changed"
   ```

3. Read the generated file in `backend/alembic/versions/` (autogenerate misses renames and data changes) and
   commit it with the model change. `tests/test_migrations.py` fails when the models and migrations differ.

Timestamps are `timestamptz` (stored in UTC).
