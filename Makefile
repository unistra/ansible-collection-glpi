# As 'glpi_api' module is in a private repository on GitLab and configured to
# be retrieved using ssh keys in the requirements file, the Makefile should be
# launch like this:
#
# 	sudo -E make
#
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
