FROM python:3.14.3-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# نصب postgresql-client (برای دسترسی به دستور psql)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /code/

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]


# FROM python:3.14.3

# ENV PYTHONDONTWRITEBYTECODE 1
# ENV PYTHONUNBUFFERED 1

# WORKDIR /code

# COPY requirements.txt /code/
# RUN pip install -r requirements.txt


# COPY . /code/

# EXPOSE 8000

# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]