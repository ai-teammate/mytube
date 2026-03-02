FROM golang:1.24-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o transcoder ./cmd/transcoder

FROM alpine:3.19
# Install FFmpeg and CA certificates.
RUN apk --no-cache add ca-certificates ffmpeg
WORKDIR /root/
COPY --from=builder /app/transcoder .
CMD ["./transcoder"]
