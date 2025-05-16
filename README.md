## Docker Compose

### Development

To start the development environment with Docker Compose, run:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

This will start the Litestar server and a PostgreSQL database.

### Production

For production, ensure your environment variables are set appropriately and run:

```bash
docker compose -f docker-compose.yml up --build -d
```

This will start the services in detached mode.
