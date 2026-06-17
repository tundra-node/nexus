FROM nginx:alpine
COPY client/static /usr/share/nginx/html
COPY abyssal-nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]