# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the pyproject.toml and pdm.lock files to the container
COPY server/pyproject.toml server/pdm.lock ./

# Install PDM
RUN pip install pdm

# Install the dependencies
RUN pdm install

# Copy the rest of the application code to the container
COPY server/src/ .

# Command to run the application
CMD ["pdm", "run", "python", "-m", "server"]
