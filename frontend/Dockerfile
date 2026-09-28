# ==============================================================================
# VinaLex — Frontend Dockerfile (Next.js 14 App Router)
# ==============================================================================

FROM node:20-alpine AS base

# Cài đặt libc6-compat nếu cần
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Sao chép package.json và cài đặt dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Sao chép mã nguồn và build
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

RUN npm run build

# Stage chạy ứng dụng (Runner)
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000

COPY --from=base /app/public ./public
COPY --from=base /app/.next ./.next
COPY --from=base /app/node_modules ./node_modules
COPY --from=base /app/package.json ./package.json
COPY --from=base /app/next.config.mjs ./next.config.mjs

EXPOSE 3000

CMD ["npm", "start"]
