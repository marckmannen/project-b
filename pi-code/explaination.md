# maak startup script
`nano /home/pi/startup.sh`

# voorbeeld inhoud script
```
#!/bin/bash
echo "Hello, world!" >> /home/pi/log.txt
```

# geef script executable rights
`chmod +x /home/pi/startup.sh`

# maak een systemd service
`sudo nano /etc/systemd/system/startup.service`

# inhoud startup.service
```
[Unit]
Description=Run my startup script
After=network.target

[Service]
ExecStart=/home/pi/startup.sh
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```


# zet service aan
`sudo systemctl daemon-reexec`<br>
`sudo systemctl daemon-reload`<br>
`sudo systemctl enable startup.service`

# herstart pi
`sudo reboot`