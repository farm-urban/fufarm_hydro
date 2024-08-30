#/bin/bash
VENV_DIR=venv
if [ ! -d ./venv ]; then
  echo "Creating virtual python environment"
  python3 -m venv ${VENV_DIR}
  . ${VENV_DIR}/bin/activate
  pip install .
fi

echo "Activating virtual python environment"
. ${VENV_DIR}/bin/activate
