#! usr/bin/env python3
import json
from pathlib import Path
from bs4 import BeautifulSoup
from sys import modules, stderr

"""
Generate lemma_dictionary for Token class in semcorproc
"""
script_dir = Path(modules[__name__].__file__).parent
output_default = script_dir.resolve().parent / 'Output'
semcor_default = script_dir.resolve().parent / 'Semcor'

def list_files(*paths):
    file_list = set()
    for path in paths:
        path = Path(path)
        if path.is_file() and path.match('brown?/tagfiles/*'):
            file_list.add(path)
        elif path.is_dir():
            files = (path.match('brown?')) and list(path.glob('tagfiles/*')) or list(path.glob('**/brown?/tagfiles/*'))
            for filename in files:
                if filename.is_file():
                    file_list.add(filename)
        else:
            print('Invalid file name. Corpus files must be in a "tagfiles" directory\
                  inside a "brown1", "brown2" or "brownv" directory.', file=stderr)
    return file_list

input_files = list_files(semcor_default / 'brown1', semcor_default / 'brown2', semcor_default / 'brownv')

def create_dictionary(input_files = input_files):
    dictionary_file = output_default / 'lemma_dictionary.json'
    dictionary = {}
    closed_classes = ['EX', 'IN', 'PDT', 'DT', 'POS', 'PRP', 'PRP$', 'RP',
                      'TO', 'UH', 'WDT', 'LS', 'WP', 'WP$', 'CC', 'CD', 'FW']
    for input_file in input_files:
        with input_file.open() as file:
            text = BeautifulSoup(file, 'lxml')
            for word in text.find_all('wf'):
                wordform = word.string
                if not '_' in wordform:
                    pos = word.get('pos')
                    lemma = word.get('lemma')
                    if pos and lemma:
                        if not wordform in dictionary:
                            dictionary[wordform] = {pos:lemma}
                        elif not pos in dictionary[wordform]:
                            dictionary[wordform][pos] = lemma
                    elif pos in closed_classes:
                        dictionary[wordform] = {pos:wordform.lower()}
        print('File "{}" loaded.'.format(input_file.stem))
    with dictionary_file.open('w') as file:
        json.dump(dictionary, file)
        print('The file "{}" was created.\n'.format(dictionary_file.as_posix()))
        print('The dictionary has {} wordforms.'.format(len(dictionary)))


if __name__ == '__main__':
    create_dictionary(input_files)