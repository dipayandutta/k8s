FROM node:20 AS builder 

WORKDIR /app 

COPY package*.json /app 

RUN npm install 

COPY . .

RUN npm run build 

# Stage-2 - NGINX 
FROM nginx:alpine 

COPY --from=builder /app/build /usr/share/nginx/html 

RUN mkdir -p /shared-data 

# Startup log 
CMD ["sh", "-c", "echo Container Started at $(date) >> /shared-data/startup.log && nginx -g 'daemon off;'"]
