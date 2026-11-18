# Install as /etc/nginx/topshinalar-proxy.inc. The app trusts X-Real-IP only from this loopback proxy.
proxy_pass http://127.0.0.1:8080;
proxy_set_header Host $host;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Real-IP $remote_addr;
proxy_read_timeout 60s;
proxy_hide_header Server;
