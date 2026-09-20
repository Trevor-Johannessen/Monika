EXCLUDE := .* _* venv/ *.service Makefile voice-history debug.py ./
EXCLUDE_FLAGS := $(foreach pattern,$(EXCLUDE),--exclude='$(pattern)')
SERVICES := monika monika-https
HTTPS_PORT := 3334
DEBUG_PORT := 3337

# Shared venv on fs1 (NFS), reused by every machine instead of a per-host install.
VENV := /mnt/fs1/shared/venvs/monika

dryrun:
	rsync -avn ${EXCLUDE_FLAGS} ./ \ /usr/local/bin/monika/

install: dryrun
	firewall-cmd --permanent --add-port=3333/tcp
	firewall-cmd --permanent --add-port=$(HTTPS_PORT)/tcp
	firewall-cmd --reload
	mkdir -p /var/lib/monika/memory.d
	chown tjohannessen -R /var/lib/monika/memory.d
	chown tjohannessen -R /usr/local/bin/monika
	if [ ! -e $(VENV) ]; then python3 -m venv $(VENV); fi
	$(VENV)/bin/pip install -r requirements.txt
	mkdir -p /etc/monika
	#mkdir -p /etc/monika/files/html
	#mkdir -p /etc/monika/files/notes
	chmod -R o+rw /etc/monika
	if [ ! -e /etc/monika/tags.json ]; then echo "[]" > /etc/monika/tags.json; fi
	cp $(SERVICES:%=%.service) /etc/systemd/system/
	-systemctl stop $(SERVICES)
	rsync -av ${EXCLUDE_FLAGS} ./ /usr/local/bin/monika/
	cp -p .env /usr/local/bin/monika/
	systemctl daemon-reload
	systemctl enable --now $(SERVICES)
	systemctl status --no-pager $(SERVICES)

uninstall:
	-systemctl disable --now $(SERVICES)
	rm -f $(SERVICES:%=/etc/systemd/system/%.service)
	systemctl daemon-reload
	rm -rf /usr/local/bin/monika
	rm -rf /etc/monika
	rm -rf /var/lib/monika/memory.d
	firewall-cmd --permanent --remove-port=3333/tcp
	firewall-cmd --permanent --remove-port=$(HTTPS_PORT)/tcp
	firewall-cmd --reload

debug:
	$(VENV)/bin/python3 -m uvicorn server:app --port $(DEBUG_PORT) --host 0.0.0.0

cli:
	mkdir -p /usr/local/bin/monika
	cp monika /usr/local/bin/monika/monika
	cp settings.json /usr/local/bin/monika/settings.json
	chmod +x /usr/local/bin/monika/monika

commit:
	cp settings.json settings.json.tmp
	jq 'walk(if type != "object" then null else . end)' settings.json > tmp.json && mv tmp.json settings.json
	git add settings.json
	git commit
	mv settings.json.tmp settings.json
