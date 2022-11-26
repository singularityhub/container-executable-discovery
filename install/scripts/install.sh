#!/bin/bash

set -e

# Show the user all relevant variables for debugging!
printf "     branch: ${branch}\n"
printf "install path: ${instal_path}\n"
printf "    clone to: ${clone_to}\n"

# Use latest from main branches
python -m pip install git+https://github.com/vsoch/pipelib@main
python -m pip install git+https://github.com/singularityhub/guts@main

# Are we installing from an already cloned thing?
if [ "${install_path}" != "" ]; then
    printf "Installing from ${install_path}\n"
    cd ${install_path}
    python -m pip install .

# Branch install, either shallow or full clone
else
    printf "Cloning to ${clone_to}\n"
    if [[ "${full_clone}" == "false" ]]; then
        printf "git clone --depth 1 -b ${branch} https://github.com/singularityhub/container-executable-discovery ${clone_to}\n"
        git clone --depth 1 -b ${branch} https://github.com/singularityhub/container-executable-discovery ${clone_to}
    else
        printf "git clone -b ${branch} https://github.com/singularityhub/container-executable-discovery ${clone_to}\n"
        git clone -b ${branch} https://github.com/singularityhub/container-executable-discovery ${clone_to}
    fi
    printf "cd ${clone_to}/lib\n"
    cd ${clone_to}/lib
    python -m pip install .    
fi
