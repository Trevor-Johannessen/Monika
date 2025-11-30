EXCLUDE := .* _* venv/ *.service Makefile voice-history debug.py ./
EXCLUDE_FLAGS := $(foreach pattern,$(EXCLUDE),--exclude='$(pattern)')

dryrun:
	rsync -avn ${EXCLUDE_FLAGS} ./ \ /usr/local/bin/monika/

install: dryrun
	if [ ! -e ./venv ]; then python3 -m venv venv; source ./venv/bin/activate; pip install -r requirements.txt; deactivate; fi
	cp monika.service /etc/systemd/system/
	systemctl stop monika
	rsync -av ${EXCLUDE_FLAGS} ./ /usr/local/bin/monika/
	systemctl daemon-reload
	systemctl start monika

debug:
	./venv/bin/uvicorn server:app --port 3334 --host 0.0.0.0
