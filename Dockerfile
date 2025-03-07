# syntax=docker/dockerfile:1.7-labs
# Use the official Python image from the Docker Hub
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app/server

# Copy the pyproject.toml and pdm.lock files to the container
COPY server/pyproject.toml server/pdm.lock server/pdm.toml ./

# Copy the rest of the application code to the container
COPY ./server/. /app/server/

# Install PDM
RUN pip install pdm

# Install the dependencies
RUN pdm sync

# Command to run the application
CMD ["pdm", "run", "litestar", "--app", "server.app:app", "run", "--reload" ,"--host", "0.0.0.0", "--port", "8000"]
