## Docker Compose

### Development

To start the development environment with Docker Compose, run:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

This will start the Litestar server and a PostgreSQL database. It will also start BLEU and chrF2 workers.

To use other metrics, look into instructions on running [workers](./workers)

To upload data, look into instructions for [mteval-upload](./mteval_upload) tool.
