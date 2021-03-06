import os
import subprocess
from pathlib import Path
from zipfile import ZipFile

from clint.textui import progress
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from PIL import Image

from sklearn.preprocessing import MultiLabelBinarizer
from iterstrat.ml_stratifiers import MultilabelStratifiedKFold

from keras.utils import Sequence
from keras.preprocessing.image import ImageDataGenerator

from .install import PATH

class ProteinAtlas():
    def __init__(self,img_path):
        self.img_path = img_path
        self.cmaps = []
        for chan_ix in range(self.n_channels):
            self.cmaps.append(self.make_cmap(chan_ix,as_cmap=True))

    def any(self, class_):
        """
        Return examples belonging to any of the classes in `class_`.

        Parameters:

            class_: int or iterable of ints

                Integer index or indices of classes to get examples from.
        """
        if isinstance(class_, pd.Index):
            mask = pd.DataFrame(self.labels.loc[:,class_] == 1).any(axis = 1)
        elif isinstance(class_, int) or (isinstance(class_, list) and isinstance(class_[0],int)):
            mask = pd.DataFrame(self.labels.iloc[:,class_] == 1).any(axis = 1)
        elif isinstance(class_, str):
            class_ = pd.Index([class_])
            mask = pd.DataFrame(self.labels.loc[:,class_] == 1).any(axis = 1)

        return self.labels.loc[mask]


    def render_batch(self,X):
        """Render a batch of images X in the HUSL colorspace for maximizing
        perceptual uniformity of each channel.

        Parameters:

            X : ndarray, (n_samples, rows, cols, 4)

        Returns:
        
            X_new : ndarray, (n_samples, rows_new, cols_new, 4)

               Batch of images in RGBa channels.
        """
        if len(X.shape) == 3:
            samples = 1
            row, cols, channels = X.shape
            X = X.reshape((1,rows,cols,channels))
        elif len(X.shape) == 4:
            samples, rows, cols, channels = X.shape
        else:
            pass

        bands = [0] * self.n_channels
        img = np.zeros((self.height,self.width,4))
        for chan in range(self.n_channels):
            bands[chan] = self.cmaps[chan](X[sample,:,:,chan])
            img = img + bands[chan]/self.n_channels
            
        img = Image.fromarray(np.uint8(img*255))
        return img

    @property
    def nrows(self): return 512

    @property
    def ncols(self): return 512


    @property
    def classes(self):
        """Set of target classes for the Protein Atlas dataset.

        Each of these classes represents a possible location in a human cell
        where a protein of interest resides.
        """
        return ["Nucleoplasm", "Nuclear membrane", "Nucleoli",
                "Nucleoli fibrillar center", "Nuclear speckles",
                "Nuclear bodies", "Endoplasmic reticulum", "Golgi apparatus",
                "Peroxisomes", "Endosomes", "Lysosomes",
                "Intermediate filaments", "Actin filaments",
                "Focal adhesion sites", "Microtubules", "Microtubule ends",
                "Cytokinetic bridge", "Mitotic spindle",
                "Microtubule organizing center", "Centrosome", "Lipid droplets",
                "Plasma membrane", "Cell junctions", "Mitochondria",
                "Aggresome", "Cytosol", "Cytoplasmic bodies", "Rods & rings"]

    @property
    def n_classes(self):
        return len(self.classes)
                       
    def make_cmap(self,chan_ix,**kwds):
        return sns.cubehelix_palette(start = chan_ix*3.0/self.n_channels,
                                     dark = 0, light = 1, gamma = 2.0, rot = 0,
                                     hue = 1, **kwds)

    @property
    def channel_colors(self):
        """
        Color of each channel in the Protein Atlas dataset.  These are not
        technically colors, just identifiers necessary to locate the path of
        each .png file.
        """
        return ["red", "green", "blue", "yellow"]


    @property
    def channels(self):
        """
        Channels present in the Protein Atlas dataset.
        """
        return ["Microtubules", "Antibody", "Nucleus", "Endoplasmic Reticulum"]

    
    @property
    def channel_colors(self):
        """
        Color of each channel in the Protein Atlas dataset.  These are not
        technically colors, just identifiers necessary to locate the path of
        each .png file.
        """
        return ["red", "green", "blue", "yellow"]

    @property
    def n_channels(self):
        """Number of channels in each image of the Protein Atlas dataset."""
        return len(self.channels)

    def get_path(self,id_,channel_ix):
        """
        Get the file path for an image from the Protein Atlas Kaggle dataset.
        
        Parameters:

            id_ : str

                The ID of the sample.

            channel_ix : int, valid values in range(self.n_channels)

                The index of the image channel to retrieve. These are:
                    0. red (microtubules band)
                    1. green (antigen band)
                    2. blue (nucleus band)
                    3. yellow (endoplasmic reticulum band)
        """
        channel_color = self.channel_colors[channel_ix]
        return self.img_path.joinpath("{}_{}.png".format(id_,channel_color))


    def get_image(self,id_):
        """Get the 4-band image corresponding to example `id_`, returning a numpy array
        of shape (512, 512, 4)

        Parameters:
        
            id_ : str

                The ID of the sample.

        Returns:

            img : ndarray of float, shape (512, 512, 4)

                Values range between 0 and 1.
        """
        bands = [None] * self.n_channels
        for chan_ix in range(self.n_channels):
            chan_path = self.get_path(id_,chan_ix)
            bands[chan_ix] = Image.open(chan_path)
        
        return np.stack(bands, axis=2) / 255

    def get_images(self,ids):
        """
        Given a pd.Index of example IDs, return an array of shape
        (samples,rows,cols,channels)
        """
        X = np.zeros((len(ids),self.nrows,self.ncols,self.n_channels))
        for sample_ix, id_ in enumerate(ids):
            X[sample_ix,:,:,:] = self.get_image(id_)

        return X

    def render_batch(self,imgs):
        nsamples, nrows, ncols, nchannels = imgs.shape

        new_imgs = np.zeros((nsamples, nrows, ncols, 4))
        bands = np.split(imgs,nchannels,axis = 3)
        for channel in range(nchannels):
            bands[channel] = np.squeeze(bands[channel],axis = 3)
            bands[channel] = self.cmaps[channel](bands[channel])
            new_imgs = new_imgs + bands[channel] / nchannels

        return new_imgs


class Test(ProteinAtlas):
    def __init__(self):
        super().__init__(img_path = PATH["test"])
        df = pd.read_csv(PATH["sample_submission.csv"]).set_index("Id")
        self.index = df.index

    def get_generator(self, batch_size = 128):
        return TestGenerator(self,batch_size)
        


class Train(ProteinAtlas):
    def __init__(self):
        super().__init__(img_path = PATH["train"])
        df          = pd.read_csv(PATH["train.csv"]).set_index("Id")
        read_target = lambda s: np.array(s.split(" "),dtype=np.int32)
        targets     = df["Target"].apply(read_target)
        mlb         = MultiLabelBinarizer()
        labels      = mlb.fit_transform(targets.values)
        index       = targets.index
        columns     = self.classes
        self.mlb = mlb
        self.labels = pd.DataFrame(labels,index,columns)
        self.index  = self.labels.index

    def train_test_split(self,train_portion, batch_size = 32):
        mskf = MultilabelStratifiedKFold(n_splits = int(1/(1-train_portion)))
        train_set, val_set = mskf.split(X = self.labels, y = self.labels).__next__()

        train_generator = TrainGenerator(self,train_set,batch_size)
        val_generator = TrainGenerator(self,train_set,batch_size)

        return train_generator, val_generator



class TrainGenerator(Sequence):
    """Data generator for generating batches of data from the Train dataset.

    This source of the data will be taken to be a cross validation fold.

    The use of MultilabelStratifiedKFold inside this class is to ensure labels
    distributions batches are evenly mixed among all classes.
    """
    def __init__(self, train, train_set, batch_size = 32, augment = False):
        """Parameters:
        
            train : intance of Train

            train_set : ndarray, int

                The indices of the training set.
        """
        self.batch_size = 32
        self.train = train
        self.train_set = train_set
        self.n_splits = int(np.ceil(len(train_set)/float(self.batch_size)))
        self.mskf = MultilabelStratifiedKFold(n_splits = self.n_splits)

        y = self.train.labels.values[self.train_set]
        X = y # dummy argument for MultilabelStratifiedKFold.fit()

        # Select batch sets from k-fold test sets
        self.batch_sets = [test_set for _ , test_set in self.mskf.split(X,y)]
        self.img_gen = ImageDataGenerator(
            fill_mode = "constant", cval = 0.,
            horizontal_flip = True,
            vertical_flip = True)


    def __len__(self):
        return len(self.batch_sets)

    def __getitem__(self, index):
        """Returns the ith batch of the data to be generated."""
        batch_set = self.batch_sets[index]
        batch_index = self.train.labels.index[batch_set]
        x_batch = self.train.get_images(batch_index)
        y_batch = self.train.labels.values[batch_set,:]
        
        # x_aug = []
        # y_aug = []
        # for X, y in self.img_gen.flow(x_batch, y_batch):
        #     x_aug.append(X)
        #     y_aug.append(y)

        # x_aug = np.concatenate(x_aug,axis = 0)
        # y_aug = np.concatenate(y,axis = 0)

        # return x_aug, y_aug

        return x_batch, y_batch

class TestGenerator(Sequence):
    """Data generator for generating batches of data from the Test dataset.
    """
    def __init__(self, test, batch_size = 32):
        """Parameters:
        
            train : intance of Train

            train_set : ndarray, int

                The indices of the training set.
        """
        self.test = test
        self.batch_size = batch_size
        self.batch_sets = np.array_split(np.arange(len(test.index)),len(self))

    # def on_epoch_end(self,epoch):
    #     self.mskf = MultilabelStratifiedKFold(n_splits = self.n_splits)

    def __len__(self):
        return int(np.ceil(len(self.test.index) / float(self.batch_size)))

    def __getitem__(self, index):
        """Returns the ith batch of the data to be generated."""
        batch_set = self.batch_sets[index]
        batch_index = self.test.index[batch_set]
        x_batch = self.test.get_images(batch_index)
        return x_batch
