remote := beryl
venvdir := .venv

push2pi:
	rsync -av --include '.git/config' --exclude '.git/*' . "${remote}:sunpower-stats/"

venv:
	python3 -m venv ${venvdir}
	${venvdir}/bin/python -m pip install -r requirements.txt
