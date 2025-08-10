import pkg_resources

# Read installed packages
installed = {pkg.key for pkg in pkg_resources.working_set}

# Read requirements.txt
with open("requirements.txt") as f:
    required = {line.strip().split("==")[0].lower() for line in f if line.strip() and not line.startswith("#")}

# Find extra packages
extras = installed - required

print("Packages not in requirements.txt:")
for pkg in sorted(extras):
    print(pkg)
