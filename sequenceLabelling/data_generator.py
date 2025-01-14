import numpy as np
# seed is fixed for reproducibility
np.random.seed(7)
import keras
from sequenceLabelling.preprocess import to_vector_single, to_casing_single, to_vector_elmo, to_vector_simple_with_elmo
from utilities.Tokenizer import tokenizeAndFilterSimple
import tensorflow as tf
tf.set_random_seed(7)

# generate batch of data to feed sequence labelling model, both for training and prediction

class DataGenerator(keras.utils.Sequence):
    'Generates data for Keras'
    def __init__(self, x, y, 
                batch_size=24, 
                preprocessor=None, 
                char_embed_size=25, 
                embeddings=None, 
                tokenize=False, 
                shuffle=True):
        'Initialization'
        self.x = x
        self.y = y
        self.preprocessor = preprocessor
        if preprocessor:
            self.labels = preprocessor.vocab_tag
        self.batch_size = batch_size
        self.embeddings = embeddings
        self.char_embed_size = char_embed_size
        self.shuffle = shuffle
        self.tokenize = tokenize
        self.on_epoch_end()
        # in case of ELMo is used, indicate if the token dump exists and should be used
        #self.use_token_dump = use_token_dump
        #if self.embeddings.use_ELMo:     
        #    self.sess = tf.Session()
        #    # It is necessary to initialize variables once before running inference.
        #    self.sess.run(tf.global_variables_initializer())

    def __len__(self):
        'Denotes the number of batches per epoch'
        # The number of batches is set so that each training sample is seen at most once per epoch
        if (len(self.x) % self.batch_size) == 0:
            return int(np.floor(len(self.x) / self.batch_size))
        else:
            return int(np.floor(len(self.x) / self.batch_size) + 1)

    def __getitem__(self, index):
        'Generate one batch of data'
        # generate data for the current batch index
        if self.preprocessor.return_casing:
            batch_x, batch_c, batch_a, batch_l, batch_y = self.__data_generation(index)
            return [batch_x, batch_c, batch_a, batch_l], batch_y
        else:  
            batch_x, batch_c, batch_l, batch_y = self.__data_generation(index)
            return [batch_x, batch_c, batch_l], batch_y

    def shuffle_pair(self, a, b):
        # generate permutation index array
        permutation = np.random.permutation(a.shape[0])
        # shuffle the two arrays
        return a[permutation], b[permutation]

    def on_epoch_end(self):
        # shuffle dataset at each epoch
        if self.shuffle == True:
            if self.y is None:
                np.random.shuffle(self.x)
            else:      
                self.shuffle_pair(self.x,self.y)

    def __data_generation(self, index):
        'Generates data containing batch_size samples' 
        max_iter = min(self.batch_size, len(self.x)-self.batch_size*index)

        # restrict data to index window
        sub_x = self.x[(index*self.batch_size):(index*self.batch_size)+max_iter]

        # tokenize texts in self.x if not already done
        max_length_x = 0
        if self.tokenize:
            x_tokenized = []
            for i in range(0, max_iter):
                tokens = tokenizeAndFilterSimple(sub_x[i])
                if len(tokens) > max_length_x:
                    max_length_x = len(tokens)
                x_tokenized.append(tokens)
        else:
            for tokens in sub_x:
                if len(tokens) > max_length_x:
                    max_length_x = len(tokens)
            x_tokenized = sub_x

        batch_x = np.zeros((max_iter, max_length_x, self.embeddings.embed_size), dtype='float32')
        if self.preprocessor.return_casing:
            batch_a = np.zeros((max_iter, max_length_x), dtype='float32')

        batch_y = None
        max_length_y = max_length_x
        if self.y is not None:
            # note: tags are always already "tokenized",
            batch_y = np.zeros((max_iter, max_length_y), dtype='float32')

        if self.embeddings.use_ELMo:     
            #batch_x = to_vector_elmo(x_tokenized, self.embeddings, max_length_x)
            batch_x = to_vector_simple_with_elmo(x_tokenized, self.embeddings, max_length_x)
            
        # generate data
        for i in range(0, max_iter):
            # store sample embeddings
            if not self.embeddings.use_ELMo:    
                batch_x[i] = to_vector_single(x_tokenized[i], self.embeddings, max_length_x)

            if self.preprocessor.return_casing:
                batch_a[i] = to_casing_single(x_tokenized[i], max_length_x)

            # store tag embeddings
            if self.y is not None:
                batch_y = self.y[(index*self.batch_size):(index*self.batch_size)+max_iter]

        if self.y is not None:
            batches, batch_y = self.preprocessor.transform(x_tokenized, batch_y)
        else:
            batches = self.preprocessor.transform(x_tokenized)

        batch_c = np.asarray(batches[0])
        batch_l = batches[1]
        
        if self.preprocessor.return_casing:
            return batch_x, batch_c, batch_a, batch_l, batch_y
        else: 
            return batch_x, batch_c, batch_l, batch_y
