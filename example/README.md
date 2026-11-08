# Пример базы данных

`init_example_db.sql` создаёт наполненную пример БД Postgres (`demo_app`:
`users` + `orders`, 200 пользователей, 800 заказов) и read-only роль
`promptstat_ro` / `ro_pass_42`.

Создайте её на своём сервере Postgres:

```bash
sudo -u postgres psql -f example/init_example_db.sql
```

Backend автоматически создаёт демо-пользователя (`user@user.com` / `user`) с подключением
к этой базе при первом запуске (localhost:5432). Если база недоступна,
созданное подключение получает статус `inactive`, и вы можете исправить
или удалить его из интерфейса.
