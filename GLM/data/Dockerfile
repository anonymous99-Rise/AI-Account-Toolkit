# syntax=docker/dockerfile:1

# ---- 构建阶段 ----
FROM golang:1.26 AS builder
WORKDIR /app

# 先拷贝依赖清单，利用 Docker 层缓存加速 go mod download
# 依赖 golang.org/x/net/proxy；golang 官方镜像内默认可达 proxy.golang.org，无需额外 GOPROXY
COPY go.mod go.sum ./
RUN go mod download

# 拷贝源码（system_prompt.md 会被 //go:embed 嵌入，必须在构建上下文中）
COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /app/mistral-proxy .

# ---- 运行阶段 ----
FROM alpine:3.20
RUN apk add --no-cache ca-certificates tzdata

COPY --from=builder /app/mistral-proxy /usr/local/bin/mistral-proxy

ENV PORT=38467 \
    DATA_DIR=/data

EXPOSE 38467
VOLUME /data

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- "http://127.0.0.1:${PORT}/healthz" >/dev/null 2>&1 || exit 1

CMD ["/usr/local/bin/mistral-proxy"]