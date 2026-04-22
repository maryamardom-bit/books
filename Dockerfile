FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONBUFFERED 1

WORKDIR /code

COPY requirements.txt /code/
RUN pip install -r requirements.txt


COPY . /code/

# EXPOSE 8000

# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]