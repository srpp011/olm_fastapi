FROM python:3.10.12

RUN apt update && apt install -y python3-pip nano apache2 libapache2-mod-wsgi-py3 libexpat1 ssl-cert apache2-dev
RUN a2enmod headers
RUN apt-get install -y libgdal-dev
WORKDIR /code

COPY ./requirements.txt /code/requirements.txt
COPY ./main.py /code/
COPY ./database.py /code/
COPY ./models.py /code/
COPY ./LandGIS_tables.xlsx /code/

RUN pip install -r /code/requirements.txt
#RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
#RUN apt-get install -y libgdal-dev
RUN gdal-config --version
RUN pip install pygdal==3.6.2.11
RUN pip install wheel
RUN pip wheel pygdal==3.6.2.11
RUN pip install pygdal==3.6.2.11  -f wheelhouse

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--proxy-headers", "--port", "5005"]