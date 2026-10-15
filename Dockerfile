FROM python:3.13-slim
RUN pip install --no-cache-dir numpy
WORKDIR /app
COPY isakke.py index.html ./
COPY laws ./laws
EXPOSE 8095
CMD ["python3", "isakke.py", "serve"]
