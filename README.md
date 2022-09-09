Ho seguito:
https://stackoverflow.com/questions/57855517/how-to-configure-a-django-application-in-a-virtual-env-served-by-uswgi-and-start

Con il seguente file .ini:

```
[uwsgi]
module = app:app
master = true
processes = 1
protocol = uwsgi
socket = 127.0.0.1:48927

chmod-socket = 664
vacuum = true
die-on-term = true
```

Per configurare il servizio su systemd. Ho utilizzato il seguente blocco server per Nginx:

```
server {
    listen 443;
    listen [::]:443 http2 ssl;

    include "ssl-params";
    ssl_certificate /etc/nginx/ssl/bestov.io.cer;
    ssl_certificate_key /etc/nginx/ssl/bestov.io.key;

    server_name tncal.th3game.eu;

    location / {
        uwsgi_pass 127.0.0.1:48927;
        include uwsgi_params;
    }
}
```

