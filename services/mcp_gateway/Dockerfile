FROM python:3.11-slim

WORKDIR /app

# 1. Copy the metadata files first (good for caching)
COPY pyproject.toml ./

# 2. Copy the actual source code (Required before pip install .)
COPY mcp_gateway/ ./mcp_gateway/

# 3. Install the package
# We do this once the source is present. 
RUN pip install --no-cache-dir .

EXPOSE 9001

# 4. Use the installed package module to run the server
CMD ["uvicorn", "mcp_gateway.main:app", "--host", "0.0.0.0", "--port", "9001"]