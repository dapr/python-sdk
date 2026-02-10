# Install a project in a editable mode
pip3 install -e .
pip3 install -e ./ext/dapr-ext-grpc/
pip3 install -e ./ext/dapr-ext-fastapi/
pip3 install -e ./ext/dapr-ext-workflow/
pip3 install -e ./ext/dapr-ext-crewai/

# Install required packages
pip3 install -r ./dev-requirements.txt
