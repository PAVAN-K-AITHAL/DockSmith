#!/bin/sh
echo "=== SAMPLE APP RUNNING ==="
echo "GREETING: ${GREETING:-Hello from Docksmith Default App!}"
echo "Current directory is: $(pwd)"
echo "Catting myapp.txt:"
cat myapp.txt
echo "========================="
