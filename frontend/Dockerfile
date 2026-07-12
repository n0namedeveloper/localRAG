# Stage 1: Build the React application
FROM oven/bun:alpine as builder

WORKDIR /app

# Copy package info and install dependencies
COPY package.json bun.lockb* ./
RUN bun install

# Copy the rest of the application code
COPY . .

# Build the app
RUN bun run build

# Stage 2: Serve the app with Nginx
FROM nginx:alpine

# Copy the built app from Stage 1
COPY --from=builder /app/build /usr/share/nginx/html

# Copy the custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
