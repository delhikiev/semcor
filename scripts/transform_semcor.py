#! usr/bin/env python3

"""
This module process SemCor3.0 files and generates other kinds or files
from them or from output of other functions in it.

The idea is that the main functions are methods of a CorpusFile class (since they take it as input
and use their fixed attributes) or call the class and compile in different ways the attributes of tokens.
The Token class encapsulates such attributes.
"""

from bs4 import BeautifulSoup
from pathlib import Path
from sys import modules, stderr
import json
from create_lemmadict import list_files
import re

script_dir = Path(modules[__name__].__file__).parent
output_default = script_dir.resolve().parent / 'output'
semcor_default = script_dir.resolve().parent / 'semcor'

class Token:
    """Encapsulates token information from the xml tag in the SemCor3.0 file."""
    dictionary_file = output_default / 'great_pos_dict.json'
#    dictionary_file = output_default / 'lemma_dictionary.json'
#    if not dictionary_file.exists():
#        from create_lemmadict import create_dictionary
#        create_dictionary()
    with dictionary_file.open() as file:
        dictionary = json.load(file)
        
    def __init__(self, wordform, pos, lemma, senses = False, status = 'ok'):
        self.wordform = wordform
        self.pos = pos
        self.lemma = lemma
        self.status = status
        self.has_senses = senses
        if senses:
            self.wnsn, self.sense_key = senses
            self.has_senses = True
            
    @staticmethod
    def get_pos(wordform, default='NA'):
        """Extract the pos information from the dictionary."""
        wf = Token.dictionary.get(wordform)
        if wf and len(wf) == 1:
            return list(wf.keys())[0], 'ok'
        else:
            if wf:
                lemmas = list(wf.values())
                status = 'ok' if lemmas.count(lemmas[0])==len(list(wf.values())) else 'pos_unsure'
            else:
                status = 'pos_unsure'
            return default, status
	
    @staticmethod
    def get_lemma(wordform, pos, default=None):
        """Extract the lemma information from the dictionary."""
        wf = Token.dictionary.get(wordform)
        default = default or wordform.lower()
        if wf:
            lemmas = list(wf.values())
            if lemmas.count(lemmas[0])==len(list(wf.values())):
                default, status = lemmas[0], 'ok'
            else:
                status = 'lemma_unsure'
            return wf.get(pos, default), status
        else:
            return default, 'lemma_unsure'
		   
    @classmethod
    def from_multiword(cls, wordform, index, token):
        """Generate a Token instance from a component of a multiword expression."""
        wordform = wordform
        pos, status_pos = Token.get_pos(wordform, token.pos)
        if '_' in token.lemma and len(token.lemma.split('_')) == len(token.wordform.split('_')):
            default_lemma = token.lemma.split('_')[index]
        else:
            default_lemma = token.lemma
        lemma, status_lemma = Token.get_lemma(wordform, pos, default_lemma)
        return Token(wordform, pos, lemma, status = (status_pos, status_lemma))
	
    @classmethod
    def from_tag(cls, tag):
        """Generate a Token instance from an element of the corpus."""
        wordform = tag.string
        pos = tag.get('pos', default='NA').split('|', 1)[0]
        lemma = tag.get('lemma')
        status_lemma = 'ok'
        if not lemma:
            lemma, status_lemma = Token.get_lemma(wordform, pos)
        wnsn = tag.get('wnsn')
        if wnsn == None:
            has_senses=False
        else:
            sense_key = '{}%{}'.format(lemma, tag.get('lexsn'))
            has_senses = (wnsn, sense_key)
        return Token(wordform, pos, lemma, has_senses, status = ('ok', status_lemma))
	
    def is_multiword(self):
        return '_' in self.wordform
	
    def get_components(self):
        """Deal with multiword expressions."""
        return [Token.from_multiword(word, index, self) for index, word in enumerate(self.wordform.split('_'))]
	
class CorpusFile:
    """File of the corpus, of which the main functions are methods."""
    def __init__(self, filename):
        self.concordance = filename.parts[-3]
        self.shortname = filename.stem
        with filename.open() as this_file:
            self.text = BeautifulSoup(this_file, 'lxml')
			
class TextItem:
    """Encapsulates information of tokens to create a context in generate_context."""
    def __init__(self, what, wordform, pos, lemma, paragraph_start, sentence_start, weight, sense_key = None):
        self.wordform = wordform
        self.spaced = ' ' + self.wordform if what == 'word' else self.wordform
        self.pos = pos
        self.lemma = lemma
        self.sense_key = sense_key
        self.paragraph_start = paragraph_start
        self.sentence_start = sentence_start
        self.weight = weight
		

def report_token_status(token, token_id):
    """Print a report of the token's status in standard error."""
    pos_issue = True if token.status[0] == 'pos_unsure' else False
    lemma_issue = True if token.status[1] == 'lemma_unsure' else False
    if pos_issue and lemma_issue:
        print('Unsure about pos and lemma information in token {}: \
              wordform: {}, pos: {}, lemma: {}'.format(token_id, token.wordform, token.pos, token.lemma), file=stderr)
    elif pos_issue:
        print('Unsure about pos information in token {}: \
              wordform: {}, pos: {}'.format(token_id, token.wordform, token.pos), file=stderr)
    elif lemma_issue:
        print('Unsure about lemma information in token {}: \
              wordform: {}, lemma: {}'.format(token_id, token.wordform, token.lemma), file=stderr)
    else:
        pass
        

def generate_tokenlist(text):
    """Create a generator of instances of TextItems based on all elements of a corpus file.
    To be used in semcor2conc."""
    for paragraph in text.find_all('p'):
        paragraph_start = True
        for sentence in paragraph.find_all('s'):
            sentence_start = True
            for word in sentence.find_all(['wf', 'punc']):
                if word.name == 'punc':
                   yield TextItem(None, word.string, word.name, word.string, paragraph_start, sentence_start, 0)
                   paragraph_start = False
                   sentence_start = False
                else:
                   great_token = Token.from_tag(word)
                   sense_key = great_token.sense_key if great_token.has_senses else None
                   for token in great_token.get_components():
                       yield TextItem('word', token.wordform, token.pos, token.lemma, paragraph_start, sentence_start, 1, sense_key)
                       paragraph_start = False
                       sentence_start = False

                
def generate_context(tokenlist, index, left_context, right_context, separator, length):
    """Generates the strings for left and right context for semcor2conc.
    Returns a tuple with both strings."""
    if separator == 'paragraph':
        nostop = lambda i: not tokenlist[i].paragraph_start
    elif separator == 'sentence':
        nostop = lambda i: not tokenlist[i].sentence_start
    else:
        nostop = True
    """Define right context."""
    i = index + 1
    weight = tokenlist[i].weight
    while i < length-1 and nostop and weight < right_context:
        i += 1
        weight += tokenlist[i].weight
    right = "".join([token.spaced for token in tokenlist[index+1:i+1]])
    """Define left context."""
    i = index
    weight = tokenlist[i].weight
    while i > 0 and nostop and weight <= left_context:
        i -= 1
        weight += tokenlist[i].weight
    left = "".join([token.spaced for token in tokenlist[i:index]])
    return left, right
	
def semcor2conc(args):
    """Generate a concordance of the selected types.
    Input_files and types must be lists/iterators;
    left_context and right_context must be integers, default = 10;
    valid separators are 'paragraph' and 'sentence', otherwise there are none."""
    input_files = list_files(*args.input_files)
    types = list(args.types)
    output_file = args.output_file or output_default / '{}_conc.csv'.format('_'.join(types))
    output_file = Path(output_file)
    left_context = args.left
    right_context = args.right
    separator = args.separator
    filter_pos = args.pos
    kind_id = args.kind_id
    with output_file.open('w') as file:
        x = 'last\tnext\tlemma' if args.add_closest else 'lemma'
        file.write('\t'.join(['concordance', 'file', 'token_id', 'left', 'wordform', 'right', x, 'pos', 'sense_key\n']))
        for input_file in input_files:
            corpus_file = CorpusFile(input_file)
            tokenlist = list(generate_tokenlist(corpus_file.text))
            chosen_words = [index for (index, token) in enumerate(tokenlist) if token.lemma in types]
            for word in chosen_words:
                node = tokenlist[word]
                pos = node.pos
                if filter_pos and not re.match(r'{}'.format([x for x in filter_pos]), pos):
                    continue
                if kind_id == 'lemma_pos':
                    wordtype = '/'.join([node.lemma, node.pos])
                elif kind_id == 'wordform':
                    wordtype = node.wordform
                else:
                    wordtype = node.lemma
                token_id = '/'.join([wordtype, corpus_file.shortname, str(word + 1)])
                left, right = generate_context(tokenlist, word, left_context, right_context, separator, len(tokenlist))
                if args.add_closest:
                    last = tokenlist[word-1].wordform
                    following = tokenlist[word+1].wordform
                    line = [corpus_file.concordance, corpus_file.shortname, token_id, left, node.wordform, right, last, following, node.lemma, pos, node.sense_key or 'NA']
                else:
                    line = [corpus_file.concordance, corpus_file.shortname, token_id, left, node.wordform, right, node.lemma, pos, node.sense_key or 'NA']
                file.write('\t'.join(line) + '\n')
            print('File "{}" processed.'.format(input_file.stem))

def semcor2R(args):
    """Generate a file to be read on R appending information from each file.
    input_files is a list of files (or with one file).
    If sense==True, multiword=True (multiword expressions are kept together)."""
    input_files = list_files(*args.input_files)
    output_file = Path(args.output_file)
    senses = args.sense
    multiword = senses or args.multiword
    if senses and output_file == output_default / 'semcor2r.csv':
        output_file = output_default / 'semcor2r_semtagged.csv'
    with output_file.open('w') as file:
        file.write("\t".join(["concordance", "file", "token_id", "wordform", "PoS", "lemma"]))
        if senses:
            file.write('\twnsn\tsense_key')
        file.write('\n')
        for input_file in input_files:
            corpus_file = CorpusFile(input_file)
            for word in corpus_file.text.find_all(['wf', 'punc']):
                index = 0
                if word.name == 'punc':
                    index += 1
                    continue
                if not multiword:
                    for token in Token.from_tag(word).get_components():
                        token_id = '/'.join([corpus_file.shortname, token.wordform, str(index)])
                        if args.verbose and type(token.status)==tuple:
                            report_token_status(token, token_id)
                        file.write('\t'.join([corpus_file.concordance, corpus_file.shortname, token_id, token.wordform, token.pos, token.lemma]) + '\n')
                        index += 1
                else:
                    token = Token.from_tag(word)
                    if senses and not token.has_senses:
                        continue
                    token_id = '/'.join([corpus_file.shortname, token.wordform, str(index)])
                    if args.verbose and type(token.status)==tuple:
                        report_token_status(token, token_id)
                    file.write('\t'.join([corpus_file.concordance, corpus_file.shortname, token_id, token.wordform, token.pos, token.lemma]))
                    index += 1
                    if senses:
                        file.write('\t{}\t{}'.format(token.wnsn, token.sense_key))
                        file.write('\n')
            print('File "{}" processed.'.format(input_file.stem))

def semcor2token(args):
    """Generate a file to be read by typetoken workflow for each original file."""
    input_files = list_files(*args.input_files)
    output_dir = Path(args.output_dir)
    if not output_dir.is_dir():
        try:
            output_dir.mkdir()
        except:
            print('Invalid output directory name. Files will be stored in default directory.', file = stderr)
            output_dir = output_default / 'typetoken'
            if not output_dir.is_dir():
                output_dir.mkdir()
    multiword = args.multiword
    for input_file in input_files:
        corpus_file = CorpusFile(input_file)
        filename = corpus_file.shortname + '.txt'
        dirname = output_dir / corpus_file.concordance
        if not dirname.exists():
            dirname.mkdir()
        output_file_name = dirname / filename
        with output_file_name.open('w') as output_file:
           for word in corpus_file.text.find_all(['wf', 'punc']):
               if word.name == 'punc':
                   output_file.write('\t'.join([word.string, word.string, 'punc\n']))
               elif not multiword:
                   for token in Token.from_tag(word).get_components():
                       if args.verbose and type(token.status)==tuple:
                           token_id = '/'.join([corpus_file.shortname, token.wordform])
                           report_token_status(token, token_id)
                       output_file.write('\t'.join([token.wordform, token.lemma, token.pos]) + '\n')
               else:
                   token = Token.from_tag(word)
                   if args.verbose and type(token.status)==tuple:
                       token_id = '/'.join([corpus_file.shortname, token.wordform])
                       report_token_status(token, token_id)
                   output_file.write('\t'.join([token.wordform, token.lemma, token.pos]) + '\n')
		
def semcor2run(args):
    """Generate a file with running text (and wordform/pos format) to be read with
    corpus analysis tools."""
    input_files = list_files(*args.input_files)
    output_dir = Path(args.output_dir)
    if not output_dir.is_dir():
        try:
            output_dir.mkdir()
        except:
            print('Invalid output directory name. Files will be stored in default directory.', file = stderr)
            output_dir = output_default / 'running_text'
            output_dir.mkdir()
    multiword = args.multiword
    for input_file in input_files:
        corpus_file = CorpusFile(input_file)
        filename = corpus_file.shortname + '.txt'
        dirname = output_dir / corpus_file.concordance
        if not dirname.exists():
            dirname.mkdir()
        output_file_name = dirname / filename
        with output_file_name.open('w') as output_file:
            for paragraph in corpus_file.text.find_all('p'):
                for word in paragraph.find_all(['wf', 'punc']):
                    if word.name == 'punc':
                        output_file.write(word.string)
                    elif not multiword:
                        for token in Token.from_tag(word).get_components():
                            output_file.write(' {}/{}'.format(token.wordform, token.pos))
                    else:
                        token = Token.from_tag(word)
                        output_file.write(' {}/{}'.format(token.wordform, token.pos))
                output_file.write('\n')

    
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('-c', '--concordance', choices= ['brown1', 'brown2', 'brownv', 'semcor', 'all'],
                               help='Option to set input files with concordance or corpus name. Default is the whole corpus.')
    parent_parser.add_argument('-i', '--input_files', nargs='*', type = Path,
                               help='Option to set input files with file names.')
    parent_parser.add_argument('-m', '--multiword', help = 'Decides whether multiword expressions will be kept as such. Default is False.', action='store_true')
    parent_parser.add_argument('-v', '--verbose', help='Prints tokens with problematic tagging', action='store_true')
    subparsers = parser.add_subparsers(dest='command')
	
    parser_semcor2r = subparsers.add_parser('semcor2r', help = 'Generates a table to be read with R from semcor files.', parents = [parent_parser])
    parser_semcor2r.add_argument('-o', '--output_file', nargs = 1, default= './output/semcor2r.csv',
                              help='Option to set an output file. Default is "semcor2r.csv" in the Output folder, "semcor2r_semtagged.csv" if sense is True.')
    parser_semcor2r.add_argument('-s', '--sense', help = 'Decides whether only sense tagged words will be selected. Default is False.', action='store_true')
    parser_semcor2r.set_defaults(function=semcor2R)
	
    parser_semcor2conc = subparsers.add_parser('semcor2conc', help = 'Generates a concordance of selected types from semcor files.', parents = [parent_parser])
    parser_semcor2conc.add_argument('-t', '--types', nargs = "*", help = 'Types to be extracted for the concordance.', required=True)
    parser_semcor2conc.add_argument('-o', '--output_file', help='Option to set an output file. Default is the list of types and "_conc.csv".', nargs = 1, default= None)
    parser_semcor2conc.add_argument('-l', '--left', help = 'Sets length of left context. Default is 10.', default = 10, type = int)
    parser_semcor2conc.add_argument('-r', '--right', help = 'Sets length of right context. Default is 10.', default = 10, type = int)
    parser_semcor2conc.add_argument('-p', '--pos', nargs = '*', help = 'Sets the part-of-speech to filter. Default is not to filter.', type=str)
    parser_semcor2conc.add_argument('-a', '--add_closest', help = 'If true, adds two columns with the closest tokens to the right and left of the node.', action='store_true')
    parser_semcor2conc.add_argument('-s', '--separator',  choices = ['paragraph', 'sentence', 'None'], default='paragraph',
                                    help = 'Sets separator for context. Options are "paragraph", "sentence" or "None". Default is "paragraph".')
    parser_semcor2conc.add_argument('-k', '--kind_id', choices = ['wordform', 'lemma_pos', 'lemma'],
                                    help = 'Option to define token id with wordform, lemma or lemma with part-of-speech (default).', default='lemma_pos')
    parser_semcor2conc.set_defaults(function=semcor2conc)
	
    parser_semcor2token = subparsers.add_parser('semcor2token', help = 'Converts semcor files to corpus files to be read in typetoken workflow.', parents = [parent_parser])    
    parser_semcor2token.add_argument('-o', '--output_dir', default = './Output/typetoken', help = 'Option to set an output directory. Default is "typeToken" in the Output directory.')
    parser_semcor2token.set_defaults(function=semcor2token)
    
    parser_semcor2run = subparsers.add_parser('semcor2run', help = 'Converts semcor files to corpus files to be read in typetoken workflow.', parents = [parent_parser])    
    parser_semcor2run.add_argument('-o', '--output_dir', default = './output/running_text', help = 'Option to set an output directory. Default is "running_text" in the Output directory.')
    parser_semcor2run.set_defaults(function=semcor2run)
    
    args = parser.parse_args()
    if args.concordance in ['brown1', 'brown2', 'brownv']:
        args.input_files = [semcor_default / args.concordance]
    elif args.concordance in ['all', 'semcor'] or args.input_files == None:
        args.input_files = semcor_default / 'brown1', semcor_default / 'brown2', semcor_default / 'brownv'
    args.function(args)
   