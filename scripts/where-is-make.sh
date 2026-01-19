echo "=== Checking if 'make' is in PATH ==="
which make || echo "make not found in PATH"

echo
echo "=== Checking common Windows install locations ==="
for p in \
  "/c/ProgramData/chocolatey/bin/make.exe" \
  "/c/Program Files (x86)/GnuWin32/bin/make.exe" \
  "/c/msys64/usr/bin/make.exe" \
  "/c/msys64/mingw64/bin/mingw32-make.exe" \
  "/c/Program Files/Git/usr/bin/make.exe"
do
  if [ -f "$p" ]; then
    echo "Found: $p"
  fi
done

echo
echo "=== Checking PATH entries ==="
echo "$PATH" | tr ':' '\n'

echo
echo "=== Testing make version ==="
make --version 2>/dev/null || echo "make cannot run"