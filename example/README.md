# Example database

`init_example_db.sql` creates a seeded example Postgres database (`demo_app`:
`users` + `orders`, 200 users, 800 orders) and a read-only role
`promptstat_ro` / `ro_pass_42`.

Create it on your Postgres server:

```bash
sudo -u postgres psql -f example/init_example_db.sql
```

The backend seeds a demo user (`user` / `user`) with a connection to this
database automatically on first start (localhost:5432). If the database is
not reachable, the seeded connection gets status `inactive` and you can fix
or delete it from the UI.
