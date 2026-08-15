python3 -m venv v1
source v1/bin/activate
python3 -m pip install -e .

trinkets
(v1) ➜  trinkets git:(v1) trinkets
usage: trinkets [-h] [--version] <utility> ...

A collection of small, self-contained developer utilities.

positional arguments:
  <utility>
    repostats  Analyse a git repository and report languages, build, deps, flow and test stats.

options:
  -h, --help   show this help message and exit
  --version    show program's version number and exit
