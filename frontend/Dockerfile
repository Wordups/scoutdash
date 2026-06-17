FROM node:22-slim

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend ./

CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0"]

