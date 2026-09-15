FROM node:22-alpine AS build
WORKDIR /app
COPY apps/meeting-room/package.json apps/meeting-room/package-lock.json ./
RUN npm ci
COPY apps/meeting-room .
ARG NEXT_PUBLIC_ROUNDTABLE_API
ENV NEXT_PUBLIC_ROUNDTABLE_API=$NEXT_PUBLIC_ROUNDTABLE_API
RUN npm run build
FROM node:22-alpine
WORKDIR /app
COPY --from=build /app ./
ENV PORT=3101
EXPOSE 3101
CMD ["sh", "-c", "npx next start -p ${PORT}"]
