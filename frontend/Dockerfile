# =============================================================================
#  Frontend de producción: build estático de Vite servido por nginx.
#  NO se usa `vite dev` (servidor de desarrollo, lento e inseguro para exponer).
#  El mismo nginx hace de reverse proxy hacia el backend y aplica la auth básica.
# =============================================================================

# --- Etapa de build --------------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# VITE_API_URL vacío a propósito: el frontend llama al backend en el MISMO origen
# (rutas relativas /api/...), que nginx redirige al contenedor del backend.
# Así no hay que hornear la IP del VPS en el build ni lidiar con CORS.
ENV VITE_API_URL=""
RUN npm run build

# --- Etapa de ejecución ----------------------------------------------------
FROM nginx:alpine

# htpasswd, para generar el fichero de credenciales desde las variables de entorno.
RUN apk add --no-cache apache2-utils

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# La imagen de nginx ejecuta todo lo que haya en /docker-entrypoint.d/ antes de
# arrancar: ahí colgamos la generación del .htpasswd.
COPY docker-entrypoint-auth.sh /docker-entrypoint.d/40-auth-basica.sh
RUN chmod +x /docker-entrypoint.d/40-auth-basica.sh

EXPOSE 80
