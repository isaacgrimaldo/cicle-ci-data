# Define global args
ARG FUNCTION_DIR="/function"
ARG RUNTIME_VERSION="3.12"

# Etapa 1: Build dependencies y Python paquetes
FROM python:${RUNTIME_VERSION}-slim AS build-image

RUN apt-get update \
    && apt-get install -y cmake ca-certificates libgl1-mesa-glx
RUN python${RUNTIME_VERSION} -m pip install --upgrade pip


# Incluir argumentos globales
ARG FUNCTION_DIR

# Instalar dependencias del sistema necesarias para face-recognition y dlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    libboost-python-dev \
    libboost-system-dev \
    python3-dev \
    python3-pip \
    zlib1g-dev \
    libjpeg-dev \
    default-libmysqlclient-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Crear el directorio de trabajo
WORKDIR ${FUNCTION_DIR}

# Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt --target ${FUNCTION_DIR}

# Etapa 2: Imagen final para runtime
FROM python:${RUNTIME_VERSION}-slim

# Incluir argumentos globales
ARG FUNCTION_DIR

# Instalar dependencias necesarias para tiempo de ejecución
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas-dev \
    liblapack-dev \
    libx11-6 \
    libgtk-3-dev \
    zlib1g \
    libjpeg62-turbo \
    default-libmysqlclient-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Configurar el directorio de trabajo
WORKDIR ${FUNCTION_DIR}

RUN python${RUNTIME_VERSION} -m pip install awslambdaric --target ${FUNCTION_DIR}

# Copiar las dependencias y el código
COPY --from=build-image ${FUNCTION_DIR} ${FUNCTION_DIR}
COPY handler.py .
COPY entry.sh /entry.sh
RUN chmod +x /entry.sh

# Entrada predeterminada para Lambda
ENTRYPOINT ["/entry.sh"]
CMD ["handler.handle_function"]
