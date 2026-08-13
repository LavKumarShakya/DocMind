FROM node:22-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
