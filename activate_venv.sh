if [ ! -d ./venv ]; then
  echo "Creating virtual python environment"
  python3 -m venv venv 
  . venv/bin/activate
  pip install .
fi

echo "Activating virtual python environment"
. venv/bin/activate
