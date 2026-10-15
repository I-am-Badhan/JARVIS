import os

# Folders to show in the tree, but NOT expand
DONT_EXPAND = {'.venv', 'node_modules', 'src-tauri', '__pycache__', '.git'}

def write_tree(startpath, file, prefix=""):
    try:
        items = sorted(os.listdir(startpath))
    except PermissionError:
        return
        
    # Ignore hidden folders like .git entirely if you don't even want them listed
    items = [f for f in items if not (f.startswith('.') and os.path.isdir(f) and f not in DONT_EXPAND)]
    
    for count, item in enumerate(items):
        path = os.path.join(startpath, item)
        is_last = count == len(items) - 1
        connector = "└── " if is_last else "├── "
        
        # Write directly to the file instead of printing
        file.write(f"{prefix}{connector}{item}\n")
        
        # If it's a directory AND not in our DONT_EXPAND list, dig deeper
        if os.path.isdir(path):
            if item not in DONT_EXPAND:
                extension = "    " if is_last else "│   "
                write_tree(path, file, prefix + extension)

# Open the file with UTF-8 encoding and write the tree
with open("tree.txt", "w", encoding="utf-8") as f:
    f.write("JARVIS/\n")
    write_tree(".", f)
    
print("Success! tree.txt has been generated.")