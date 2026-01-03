EXCLUDE := .* _* venv/ *.service Makefile voice-history debug.py ./
EXCLUDE_FLAGS := $(foreach pattern,$(EXCLUDE),--exclude='$(pattern)')

dryrun:
	rsync -avn ${EXCLUDE_FLAGS} ./ \ /usr/local/bin/monika/

install: dryrun
	firewall-cmd --permanent --add-port=3333/tcp
	firewall-cmd --reload
	mkdir -p /var/lib/monika/memory.d
	chown tjohannessen -R /var/lib/monika/memory.d
	if [ ! -e /usr/local/bin/monika/venv ]; then python3 -m venv /usr/local/bin/monika/venv; fi
	/usr/local/bin/monika/venv/bin/pip install -r requirements.txt
	mkdir -p /etc/monika
	if [ ! -e /etc/monika/tags.json ]; then echo "[]" > /etc/monika/tags.json; fi
	cp monika.service /etc/systemd/system/
	systemctl stop monika
	rsync -av ${EXCLUDE_FLAGS} ./ /usr/local/bin/monika/
	cp -p .env /usr/local/bin/monika/
	systemctl daemon-reload
	systemctl start monika

debug:
	./venv/bin/uvicorn server:app --port 3334 --host 0.0.0.0

commit:
	cp settings.json settings.json.tmp
	jq 'walk(if type != "object" then null else . end)' settings.json > tmp.json && mv tmp.json settings.json
	git add settings.json
	git commit

