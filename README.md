# semcor
The code in this repository processes semcor files to turn them into other kinds of files, such as
1) running text
2) one word-lemma-pos per line
3) concordance

The transform_semcor.py file can be executed from console and responds to -h.
The script assumes there's a 'semcor' folder (with its original 'brown1', 'brown2', 'brownv' subfolders and their 'tagfiles' subfolders) and an 'output' folder in the parent folder, but those paths can also be set with optional arguments.
