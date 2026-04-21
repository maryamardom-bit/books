FROM python:3.10-slim

WORKDIR /code

COPY requirements.txt /code/
RUN pip install --upgrade pip
RUN pip install django psycopg2-binary

COPY . /code/

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]