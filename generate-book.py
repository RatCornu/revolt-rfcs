#!/usr/bin/env python3



"""
original code is from https://github.com/rust-lang/rfcs/blob/master/generate-book.py and is licensed under MIT+Apache

This auto-generates the mdBook SUMMARY.md file based on the layout on the filesystem.
This generates the `src` directory based on the contents of the `rfcs` directory.
Most RFCs should be kept to a single chapter. However, in some rare cases it
may be necessary to spread across multiple pages. In that case, place them in
a subdirectory with the same name as the RFC. For example:
    0123-my-awesome-feature.md
    0123-my-awesome-feature/extra-material.md
It is recommended that if you have static content like images that you use a similar layout:
    0123-my-awesome-feature.md
    0123-my-awesome-feature/diagram.svg
The chapters are presented in sorted-order.
"""

from io import TextIOWrapper
import os
import shutil
import subprocess

def main():
    if os.path.exists('src'):
        # Clear out src to remove stale links in case you switch branches.
        shutil.rmtree('src')
    os.mkdir('src')

    for path in os.listdir('rfcs'):
        symlink(f'../rfcs/{path}', f'src/{path}')

    symlink('../README.md', 'src/introduction.md')

    with open('src/SUMMARY.md', 'w') as summary:
        summary.write('[Introduction](introduction.md)\n\n')
        collect(summary, 'rfcs', 0)

    subprocess.call(['mdbook', 'build'])

def collect(summary: TextIOWrapper, path: str, depth: int):
    entries = [e for e in os.scandir(path) if e.name.endswith('.md')]
    entries.sort(key=lambda e: e.name)
    for entry in entries:
        indent = '    '*depth
        name = entry.name[:-3]
        link_path = entry.path[5:]

        summary.write(f'{indent}- [{name}]({link_path})\n')
        maybe_subdir = os.path.join(path, name)

        if os.path.isdir(maybe_subdir):
            collect(summary, maybe_subdir, depth+1)

def symlink(src: str, dst: str):
    if not os.path.exists(dst):
        os.symlink(src, dst)

if __name__ == '__main__':
    main()