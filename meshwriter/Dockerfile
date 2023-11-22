FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive

# install basic dependancies
RUN apt update
RUN apt -y upgrade
RUN apt -y install build-essential software-properties-common python3-pip

# install Python dependancies
RUN pip install pandas==1.4.1 shapely==1.8.1.post1 tiletanic==1.1.0 pyproj==3.3.0 Pillow==8.0.0 openpyxl==3.0.9

# install GDAL
RUN add-apt-repository ppa:ubuntugis/ubuntugis-unstable
RUN apt update
RUN apt install -y gdal-bin



WORKDIR /usr/src/app