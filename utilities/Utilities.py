# some convenient methods for all models
import regex as re
import numpy as np
# seed is fixed for reproducibility
from numpy.random import seed
seed(7)
import pandas as pd
import sys
import os.path

from keras.preprocessing import text
from keras import backend as K

#from nltk.tokenize import wordpunct_tokenize
#from nltk.stem.snowball import EnglishStemmer

from tqdm import tqdm 
from gensim.models import FastText
from gensim.models import KeyedVectors
import langdetect
from textblob import TextBlob
from textblob.translate import NotTranslated
from xml.sax.saxutils import escape

import argparse

def dot_product(x, kernel):
    """
    Wrapper for dot product operation used inthe attention layers, in order to be compatible with both
    Theano and Tensorflow
    Args:
        x (): input
        kernel (): weights
    Returns:
    """
    if K.backend() == 'tensorflow':
        # todo: check that this is correct
        return K.squeeze(K.dot(x, K.expand_dims(kernel)), axis=-1)
    else:
        return K.dot(x, kernel)


# read list of words (one per line), e.g. stopwords, badwords
def read_words(words_file):
    return [line.replace('\n','').lower() for line in open(words_file, 'r')]


# preprocessing used for twitter-trained glove embeddings
def glove_preprocess(text):
    """
    adapted from https://nlp.stanford.edu/projects/glove/preprocess-twitter.rb

    """
    # Different regex parts for smiley faces
    eyes = "[8:=;]"
    nose = "['`\-]?"
    text = re.sub("https?:* ", "<URL>", text)
    text = re.sub("www.* ", "<URL>", text)
    text = re.sub("\[\[User(.*)\|", '<USER>', text)
    text = re.sub("<3", '<HEART>', text)
    text = re.sub("[-+]?[.\d]*[\d]+[:,.\d]*", "<NUMBER>", text)
    text = re.sub(eyes + nose + "[Dd)]", '<SMILE>', text)
    text = re.sub("[(d]" + nose + eyes, '<SMILE>', text)
    text = re.sub(eyes + nose + "p", '<LOLFACE>', text)
    text = re.sub(eyes + nose + "\(", '<SADFACE>', text)
    text = re.sub("\)" + nose + eyes, '<SADFACE>', text)
    text = re.sub(eyes + nose + "[/|l*]", '<NEUTRALFACE>', text)
    text = re.sub("/", " / ", text)
    text = re.sub("[-+]?[.\d]*[\d]+[:,.\d]*", "<NUMBER>", text)
    text = re.sub("([!]){2,}", "! <REPEAT>", text)
    text = re.sub("([?]){2,}", "? <REPEAT>", text)
    text = re.sub("([.]){2,}", ". <REPEAT>", text)
    pattern = re.compile(r"(.)\1{2,}")
    text = pattern.sub(r"\1" + " <ELONG>", text)

    return text

#
# split provided sequence data in two sets given the given ratio between 0 and 1
# for instance ratio at 0.8 will split 80% of the sentence in the first set and 20%
# of the remaining sentence in the second one 
#
def split_data_and_labels(x, y, ratio):
    if (len(x) != len(y)):
        print('error: size of x and y set must be equal, ', len(x), '=/=', len(y))
        return
    x1 = []
    x2 = []
    y1 = []
    y2 = []
    for i in range(len(x)):
        if np.random.random_sample() < ratio:
            x1.append(x[i])
            y1.append(y[i])
        else:
            x2.append(x[i])
            y2.append(y[i])
    return np.asarray(x1),np.asarray(y1),np.asarray(x2),np.asarray(y2)    


url_regex = re.compile(r"https?:\/\/[a-zA-Z0-9_\-\.]+(?:com|org|fr|de|uk|se|net|edu|gov|int|mil|biz|info|br|ca|cn|in|jp|ru|au|us|ch|it|nl|no|es|pl|ir|cz|kr|co|gr|za|tw|hu|vn|be|mx|at|tr|dk|me|ar|fi|nz)\/?\b")

# language detection with langdetect package
def detect_lang(x):
    try:
        language = langdetect.detect(x)
    except:
        language = 'unk'
    return language

# language detection with textblob package
def detect_lang_textBlob(x):
    #try:
    theBlob = TextBlob(x)
    language = theBlob.detect_language()
    #except:
    #    language = 'unk'
    return language

def translate(comment):
    if hasattr(comment, "decode"):
        comment = comment.decode("utf-8")

    text = TextBlob(comment)
    try:
        text = text.translate(to="en")
    except NotTranslated:
        pass

    return str(text)


# generate the list of out of vocabulary words present in the Toxic dataset 
# with respect to 3 embeddings: fastText, Gloves and word2vec
def generateOOVEmbeddings():
    # read the (DL cleaned) dataset and build the vocabulary
    print('loading dataframes...')
    train_df = pd.read_csv('../data/training/train2.cleaned.dl.csv')
    test_df = pd.read_csv('../data/eval/test2.cleaned.dl.csv')

    # ps: forget memory and runtime, it's python here :D
    list_sentences_train = train_df["comment_text"].values
    list_sentences_test = test_df["comment_text"].values
    list_sentences_all = np.concatenate([list_sentences_train, list_sentences_test])

    tokenizer = text.Tokenizer(num_words=400000)
    tokenizer.fit_on_texts(list(list_sentences_all))
    print('word_index size:', len(tokenizer.word_index), 'words')
    word_index = tokenizer.word_index

    # load fastText - only the words
    print('loading fastText embeddings...')
    voc = set()
    f = open('/mnt/data/wikipedia/embeddings/crawl-300d-2M.vec')
    begin = True
    for line in f:
        if begin:
            begin = False
        else: 
            values = line.split()
            word = ' '.join(values[:-300])
            voc.add(word)
    f.close()
    print('fastText embeddings:', len(voc), 'words')

    oov = []
    for tokenStr in word_index:
        if not tokenStr in voc:
            oov.append(tokenStr)

    print('fastText embeddings:', len(oov), 'out-of-vocabulary')

    with open("../data/training/oov-fastText.txt", "w") as oovFile:
        for w in oov:
            oovFile.write(w)
            oovFile.write('\n')
    oovFile.close()

    # load gloves - only the words
    print('loading gloves embeddings...')
    voc = set()
    f = open('/mnt/data/wikipedia/embeddings/glove.840B.300d.txt')
    for line in f:
        values = line.split()
        word = ' '.join(values[:-300])
        voc.add(word)
    f.close()
    print('gloves embeddings:', len(voc), 'words')

    oov = []
    for tokenStr in word_index:
        if not tokenStr in voc:
            oov.append(tokenStr)

    print('gloves embeddings:', len(oov), 'out-of-vocabulary')

    with open("../data/training/oov-gloves.txt", "w") as oovFile:
        for w in oov:
            oovFile.write(w)
            oovFile.write('\n')
    oovFile.close()

    # load word2vec - only the words
    print('loading word2vec embeddings...')
    voc = set()
    f = open('/mnt/data/wikipedia/embeddings/GoogleNews-vectors-negative300.vec')
    begin = True
    for line in f:
        if begin:
            begin = False
        else: 
            values = line.split()
            word = ' '.join(values[:-300])
            voc.add(word)
    f.close()
    print('word2vec embeddings:', len(voc), 'words')

    oov = []
    for tokenStr in word_index:
        if not tokenStr in voc:
            oov.append(tokenStr)
    
    print('word2vec embeddings:', len(oov), 'out-of-vocabulary')

    with open("../data/training/oov-w2v.txt", "w") as oovFile:
        for w in oov:    
            oovFile.write(w)
            oovFile.write('\n')
    oovFile.close()
    
     # load numberbatch - only the words
    print('loading numberbatch embeddings...')
    voc = set()
    f = open('/mnt/data/wikipedia/embeddings/numberbatch-en-17.06.txt')
    begin = True
    for line in f:
        if begin:
            begin = False
        else: 
            values = line.split()
            word = ' '.join(values[:-300])
            voc.add(word)
    f.close()
    print('numberbatch embeddings:', len(voc), 'words')

    oov = []
    for tokenStr in word_index:
        if not tokenStr in voc:
            oov.append(tokenStr)
    
    print('numberbatch embeddings:', len(oov), 'out-of-vocabulary')

    with open("../data/training/oov-numberbatch.txt", "w") as oovFile:
        for w in oov:    
            oovFile.write(w)
            oovFile.write('\n')
    oovFile.close()


def ontonotes_conll2012_names(pathin, pathout):
    # generate the list of files having a .name extension in the complete ontonotes corpus
    fileout = open(os.path.join(pathout, "names.list"),'w+')

    for subdir, dirs, files in os.walk(pathin):
        for file in files:
            if file.endswith('.name'):
                ind = subdir.find("data/english/")
                if (ind == -1):
                    print("path to ontonotes files appears invalid")
                subsubdir = subdir[ind:]
                fileout.write(os.path.join(subsubdir, file.replace(".name","")))
                fileout.write("\n")
    fileout.close()


def convert_conll2012_to_iob2(pathin, pathout):
    """
    This method will post-process the assembled Ontonotes CoNLL-2012 data for NER. 
    It will take an input like:
      bc/cctv/00/cctv_0001   0    5         Japanese    JJ             *           -    -      -   Speaker#1    (NORP)           *        *            *        *     -
    and transform it into a simple and readable:
      Japanese  B-NORP
    taking into account the sequence markers and an expected IOB2 scheme.
    """
    if pathin == pathout:
        print("input and ouput path must be different:", pathin, pathout)
        return

    names_doc_ids = []
    with open(os.path.join("data", "sequenceLabelling", "CoNLL-2012-NER", "names.list"),'r') as f:
        for line in f:
            line = line.rstrip()
            if len(line) == 0:
                continue
            names_doc_ids.append(line)
    print("number of documents with name notation:", len(names_doc_ids))

    nb_files = 0
     # first pass to get number of files - test files for CoNLL-2012 are under conll-2012-test/, not test/
     # we ignore files not having .names extension in the original ontonotes realease 
    for subdir, dirs, files in os.walk(pathin):
        for file in files:
            if '/english/' in subdir and (file.endswith('gold_conll')) and not '/pt/' in subdir and not '/test/' in subdir:
                ind = subdir.find("data/english/")
                if (ind == -1):
                    print("path to ontonotes files appears invalid")
                subsubdir = os.path.join(subdir[ind:], file.replace(".gold_conll", ""))
                if subsubdir in names_doc_ids:
                    nb_files += 1
    nb_total_files = nb_files
    print(nb_total_files, 'total files to convert')

    # load restricted set of ids for the CoNLL-2012 dataset
    train_doc_ids = []
    dev_doc_ids = []
    test_doc_ids = []

    with open(os.path.join("data", "sequenceLabelling", "CoNLL-2012-NER", "english-ontonotes-5.0-train-document-ids.txt"),'r') as f:
        for line in f:
            line = line.rstrip()
            if len(line) == 0:
                continue
            train_doc_ids.append(line)
    print("number of train documents:", len(train_doc_ids))

    with open(os.path.join("data", "sequenceLabelling", "CoNLL-2012-NER", "english-ontonotes-5.0-development-document-ids.txt"),'r') as f:
        for line in f:
            line = line.rstrip()
            if len(line) == 0:
                continue
            dev_doc_ids.append(line)
    print("number of development documents:", len(dev_doc_ids))

    with open(os.path.join("data", "sequenceLabelling", "CoNLL-2012-NER", "english-ontonotes-5.0-conll-2012-test-document-ids.txt"),'r') as f:
        for line in f:
            line = line.rstrip()
            if len(line) == 0:
                continue
            test_doc_ids.append(line)
    print("number of test documents:", len(test_doc_ids))

    train_out = open(os.path.join(pathout, "eng.train"),'w+')
    dev_out = open(os.path.join(pathout, "eng.dev"),'w+')
    test_out = open(os.path.join(pathout, "eng.test"),'w+')

    nb_files = 0
    pbar = tqdm(total=nb_total_files)
    for subdir, dirs, files in os.walk(pathin):
        for file in files:
            #if '/english/' in subdir and (file.endswith('gold_conll') or ('/test/' in subdir and file.endswith('gold_parse_conll'))) and not '/pt/' in subdir:
            if '/english/' in subdir and (file.endswith('gold_conll')) and not '/pt/' in subdir and not '/test/' in subdir:
                
                ind = subdir.find("data/english/")
                if (ind == -1):
                    print("path to ontonotes files appears invalid")
                subsubdir = os.path.join(subdir[ind:], file.replace(".gold_conll", ""))

                if not subsubdir in names_doc_ids:
                    continue

                pbar.update(1)

                f2 = None
                if '/train/' in subdir and subsubdir in train_doc_ids:
                    f2 = train_out
                elif '/development/' in subdir and subsubdir in dev_doc_ids:
                    f2 = dev_out
                elif '/conll-2012-test/' in subdir and subsubdir in test_doc_ids:
                    f2 = test_out

                if f2 is None:
                    continue

                with open(os.path.join(subdir, file),'r') as f1:
                    previous_tag = None
                    for line in f1:
                        line_ = line.rstrip()
                        line_ = ' '.join(line_.split())
                        if len(line_) == 0:
                            f2.write("\n")
                            previous_tag = None
                        elif line_.startswith('#begin document'):
                            f2.write(line_+"\n\n")
                            previous_tag = None
                        elif line_.startswith('#end document'):
                            #f2.write("\n")
                            previous_tag = None
                        else:
                            pieces = line_.split(' ')
                            if len(pieces) < 11:
                                print(os.path.join(subdir, file), "-> unexpected number of fiels for line (", len(pieces), "):", line_)
                                previous_tag = None
                            word = pieces[3]
                            # some punctuation are prefixed by / (e.g. /. or /? for dialogue turn apparently)
                            if word.startswith("/") and len(word) > 1:
                                word = word[1:]
                            # in dialogue texts, interjections are maked with a prefix %, e.g. #um, #eh, we remove this prefix
                            if word.startswith("%") and len(word) > 1:
                                word = word[1:]
                            # there are '='' prefixes to some words, although I don't know what it is used for, we remove it
                            if word.startswith("=") and len(word) > 1:
                                word = word[1:]
                            tag = pieces[10]
                            if tag.startswith('('):
                                if tag.endswith(')'):
                                    tag = tag[1:-1]
                                    previous_tag = None
                                else:
                                    tag = tag[1:-1]
                                    previous_tag = tag
                                f2.write(word+"\tB-"+tag+"\n")
                            elif tag == '*' and previous_tag is not None:
                                f2.write(word+"\tI-"+previous_tag+"\n")
                            elif tag == '*)':
                                f2.write(word+"\tI-"+previous_tag+"\n")
                                previous_tag = None
                            else:
                                f2.write(word+"\tO\n")
                                previous_tag = None
    pbar.close()

    train_out.close()
    dev_out.close()
    test_out.close()
    

def convert_conll2003_to_iob2(filein, fileout):
    """
    This method will post-process the assembled CoNLL-2003 data for NER. 
    It will take an input like:
      
    and transform it into a simple and readable:
      Japanese  B-NORP
    taking into account the sequence markers and an expected IOB2 scheme.
    """
    with open(filein,'r') as f1:
        with open(fileout,'w') as f2:
            previous_tag = 'O'
            for line in f1:
                line_ = line.rstrip()
                if len(line_) == 0 or line_.startswith('-DOCSTART-'):
                    f2.write(line_+"\n")
                    previous_tag = 'O'
                else:
                    word, pos, phrase, tag = line_.split(' ')
                    if tag == 'O' or tag.startswith('B-'):
                        f2.write(word+"\t"+tag+"\n")
                    else:
                        subtag = tag[2:]
                        if previous_tag.endswith(tag[2:]):
                            f2.write(word+"\t"+tag+"\n")
                        else:
                            f2.write(word+"\tB-"+tag[2:]+"\n")
                    previous_tag = tag


if __name__ == "__main__":
    # usage example - for CoNLL-2003, indicate the eng.* file to be converted:
    # > python3 utilities/Utilities.py --dataset-type conll2003 --data-path /home/lopez/resources/CoNLL-2003/eng.train --output-path /home/lopez/resources/CoNLL-2003/iob2/eng.train 
    # for CoNLL-2012, indicate the root directory of the ontonotes data (in CoNLL-2012 format) to be converted:
    # > python3 utilities/Utilities.py --dataset-type conll2012 --data-path /home/lopez/resources/ontonotes/conll-2012/ --output-path /home/lopez/resources/ontonotes/conll-2012/iob2/

    # get the argument
    parser = argparse.ArgumentParser(
        description = "Named Entity Recognizer dataset converter to OIB2 tagging scheme")

    #parser.add_argument("action")
    parser.add_argument("--dataset-type",default='conll2003', help="dataset to be used for training the model, one of ['conll2003','conll2012']")
    parser.add_argument("--data-path", default=None, help="path to the corpus of documents to process") 
    parser.add_argument("--output-path", default=None, help="path to write the converted dataset") 

    args = parser.parse_args()
    
    #action = args.action 
    dataset_type = args.dataset_type
    data_path = args.data_path
    output_path = args.output_path

    if dataset_type == 'conll2003':
        convert_conll2003_to_iob2(data_path, output_path)
    elif dataset_type == 'conll2012':    
        convert_conll2012_to_iob2(data_path, output_path)
    elif dataset_type == 'ontonotes':    
        ontonotes_conll2012_names(data_path, output_path)


