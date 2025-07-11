# syntax=docker/dockerfile:1.7-labs
# Use the official Python image from the Docker Hub
FROM python:3.13-slim

ARG UID=1000
ARG GID=1000

ENV PATH="/opt/nodeenv/bin:$PATH"

# Set the working directory in the container
WORKDIR /app/server

# Copy the pyproject.toml and pdm.lock files to the container
COPY server/pyproject.toml server/pdm.lock server/pdm.toml ./

# Install PDM
RUN pip install --no-cache-dir pdm

# Install the dependencies
RUN pdm sync -g --project .
RUN pdm run nodeenv --quiet /opt/nodeenv/
RUN NODE_OPTIONS="--no-deprecation --disable-warning=ExperimentalWarning" npm install --ignore-scripts --no-fund

# Create a non-root user and group
RUN groupadd -g "${GID}" appuser && useradd --create-home --no-log-init -u "${UID}" -g ${GID} appuser
USER appuser

# Copy the rest of the application code to the container
COPY ./server/. /app/server/

# Command to run the application
CMD ["litestar", "--app", "server.app:app", "run", "--reload" ,"--host", "0.0.0.0", "--port", "8000"]
