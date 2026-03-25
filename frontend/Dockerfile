# Base stage
FROM node:20-slim AS base-stage
WORKDIR /app
COPY package*.json ./
RUN npm install

# Development stage
FROM base-stage AS development-stage
COPY . .
# Vite is expected to run on port 5173
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

# Build stage
FROM base-stage AS build-stage
COPY . .
RUN npm run build

# Production stage
FROM nginx:stable-alpine AS production-stage

# Copy the build output from the build stage to the nginx html directory
# Note: Vite is configured to output to ../frontend_dist, so in the container context
# where /app is the root of the src, it will be at /frontend_dist
COPY --from=build-stage /frontend_dist /usr/share/nginx/html


# Copy custom nginx config if needed, or use default
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
