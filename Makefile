DST=/local/ansible/inventories/glpi-api

all: clean virtualenv install system

clean:
	-rm -r $(DST)

virtualenv:
	virtualenv $(DST)/env --prompt '(ansible-glpi-api)'
	$(DST)/env/bin/pip install -r requirements.txt

install:
	cp -rf glpi-api.py $(DST)
	chmod u+x $(DST)/glpi-api.py

system:
	sed -e 's|%DIR%|$(DST)|' glpi-api.sh > /local/bin/glpi-api
	chmod u+x /local/bin/glpi-api
