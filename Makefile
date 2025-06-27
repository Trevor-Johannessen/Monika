EXCLUDE := .* _* venv/ *.service Makefile voice-history debug.py ./
EXCLUDE_FLAGS := $(foreach pattern,$(EXCLUDE),--exclude='$(pattern)')

dryrun:
	rsync -avn ${EXCLUDE_FLAGS} ./ \ /usr/local/bin/monika/

install: dryrun
	systemctl stop monika
	rsync -av ${EXCLUDE_FLAGS} ./ /usr/local/bin/monika/
	cp monika.service /etc/systemd/system/
	mkdir -p /var/lib/monika
	mkdir -p /etc/monika
	test -f /etc/monika/tags.json || echo "[]" > /etc/monika/tags.json
	systemctl daemon-reload
	systemctl start monika

