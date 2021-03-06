import tensorflow as tf
import numpy as np
import os
import shutil
from copy import deepcopy


def refresh_dir(dir):
    try:
        shutil.rmtree(dir, ignore_errors=True)
    except IOError:
        pass
    finally:
        os.mkdir(dir)


def write_temp(weights):
    """
    Function will delete and recreate temp folder before it writes the weight matrices
    :param weights:
    :return: None
    """

    temp_destination = "temp/"
    refresh_dir(temp_destination)

    for count, arr in enumerate(weights):
        arr = np.array(arr)
        temp_fname = temp_destination + "w" + str(count) + ".csv"
        np.savetxt(temp_fname, arr, delimiter=",")


class GraphInfo:
    def __init__(self,id,layers,ls_units):
        """
        Why do I need this class, i'm still trying to find a rationale.
        :param id: id of the model
        :param layers: no. of layers including input and output int8
        :param ls_units: a list of no. of units in each layer
        """
        try:
            assert layers == len(ls_units)
        except AssertionError as e:
            e.args = e.args + ("no. of layer inconsistent, check units list. Be sure to include"
                            " input and output layers",)
            raise
        else:
            # no. of hidden layers in the model
            self.layers = layers

            # no. of units in each layer
            self.units = ls_units

            # id of the model
            self.id = id

    def insert_layer(self,after_layer,inplace = False):

        """
        Inserts a layer after the location given by after_layer
        :param after_layer: index of layer after which the new layer is to be inserted
        :param inplace: if true, it will modify the object inplace, if false it will create a new object and modify
        :return: None if inplace is True, modified temp object if inplace is False
        """
        try:
            assert (after_layer < (self.layers - 1)) and (after_layer >= 0)
        except AssertionError as err:
            err.args = err.args + (" after_layer index out of bounds",)
            raise
        else:
            if inplace:
                self.layers += 1
                prev_layer_units = self.units[after_layer]
                self.units.insert(after_layer,prev_layer_units)
                return None

            else:
                temp_ginfo = deepcopy(self)
                temp_ginfo.layers += 1
                prev_layer_units = temp_ginfo.units[after_layer]
                temp_ginfo.units.insert(after_layer, prev_layer_units)
                return temp_ginfo

    def add_units(self,layer_index,units, inplace = False):
        """
        :param layer_index: index of layer where to add units
        :param units: no. of units to add in this layer
        :return: a GraphInfo object, the existing object is not modified
        """
        try:
            assert units > 0
        except AssertionError as err:
            err.args = err.args + ("Cannot shrink the network, enter a positive number.",)
            raise
        else:
            if inplace:
                self.units[layer_index] += units
                return None
            else:
                temp_ginfo = deepcopy(self)
                temp_ginfo.units[layer_index] += units
                return temp_ginfo

    def get_info(self):
        str = "ID: {}\tlayers: {}\tunits: {}".format(self.id,self.layers,self.units)
        return str


class Data:
    def __init__(self,x_fname,y_fname):
        self.X = np.genfromtxt(x_fname,delimiter=",").astype(np.float32).reshape(-1,784)
        self.Y = np.genfromtxt(y_fname,delimiter=",").astype(np.float32).reshape(-1,10)


class BuildModel:
    """
    after training, weights are written to temp folder.
    To explicity write weight matrices to model directory, use writeWeights() method.
    """
    def __init__(self,graph_info):
        """
        reads the graph structure form graph_info object,
        if model_id = 1, write weights to temp folder.
        retrieves weights from temp_directory
        """
        tf.reset_default_graph()

        self.id = graph_info.id
        self.layers = graph_info.layers
        self.ls_units = graph_info.units
        self.dir = "history/model"+str(self.id)+"/"

        # refresh model sub-directory
        refresh_dir(self.dir)

        # if id = 1 write random weights to temp directory
        if self.id == 1:
            refresh_dir("temp")
            w0 = np.random.normal(loc = 0.0, scale = 0.1, size=[784,self.ls_units[1]])
            w1 = np.random.normal(loc = 0.0, scale = 0.1, size = [self.ls_units[1],10])
            np.savetxt("temp/"+"w0.csv",w0,delimiter=",")
            np.savetxt("temp/"+"w1.csv",w1,delimiter= ",")

        # retrieve weights from temp directory
        self.weights = [0]*(self.layers-1)
        for i in range(self.layers-1):
            temp_fname = "temp/" +"w"+str(i)+".csv"
            self.weights[i] = tf.constant(np.genfromtxt(temp_fname,delimiter=",").astype(np.float32))

    def forward(self,x):
        self.kernel = [0]*(self.layers-1)
        l = [0]*(self.layers-1)
        l_relu = [0]*(self.layers)
        l_relu[0] = x
        for i in range(self.layers-1):
            with tf.variable_scope("layer"+str(i)):
                self.kernel[i] = tf.get_variable(name = "weight"+str(i),
                                                 initializer=self.weights[i],trainable=True)
                l[i] = tf.matmul(l_relu[i],self.kernel[i],name = "matmul")
                l_relu[i+1] = tf.nn.relu(l[i])
        prediction = tf.nn.softmax(l[self.layers-2])

        return prediction,l[self.layers-2]

    def train(self,epochs):
        with tf.variable_scope("inputs"):
            x = tf.placeholder(tf.float32,shape = [None,784],name = "input_img")
            y_true = tf.placeholder(tf.float32,shape = [None,10], name = "true_cls")

        y_true_cls = tf.argmax(y_true)

        pred,logits = self.forward(x)

        pred_cls = tf.argmax(pred)
        acc = tf.reduce_sum(tf.cast(tf.equal(y_true_cls,pred_cls),tf.int8),name = "accuracy")
        tf.summary.scalar("Accuracy",acc)
        cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits_v2(labels =y_true, logits =logits,name = "cost"))
        opt = tf.train.AdamOptimizer(1e-2).minimize(loss = cost,name = "Optimizer")

        saver = tf.train.Saver()
        merged = tf.summary.merge_all()
        writer = tf.summary.FileWriter(self.dir+"checkpoint", graph=tf.get_default_graph())

        # train the network, for every epoch display the accuracy on test set.
        with tf.Session() as sess:
            train_data = Data(x_fname=r"D:\data\mnist\x_train.csv", y_fname=r"D:\data\mnist\y_train.csv")
            test_data = Data(x_fname=r"D:\data\mnist\x_test.csv", y_fname=r"D:\data\mnist\y_test.csv")

            sess.run(tf.global_variables_initializer())
            sess.run(tf.local_variables_initializer())
            for i in range(epochs):

                train_dict = {x:train_data.X, y_true:train_data.Y}
                train_acc,loss,_ = sess.run([acc,cost,opt],feed_dict=train_dict)

                test_dict = {x: test_data.X, y_true: test_data.Y}
                test_acc,summary = sess.run([acc,merged],feed_dict=test_dict)
                writer.add_summary(summary,i)
                print("Epoch: ",i,"\tcost: ",loss,"\ttrain_acc: ",train_acc,"\ttest_acc: ",test_acc)

            self.new_kernel = sess.run(self.kernel)
            save_path = self.dir +"checkpoint/model"
            saver.save(sess,save_path)

            write_temp(self.new_kernel)

    def write_weights(self):
        """
        writes weight matrices to model sub-directory
        :return:None
        """
        temp_count = 0
        for arr in self.new_kernel:
            temp_fname = self.dir +"w"+str(temp_count)+".csv"
            np.savetxt(temp_fname,arr,delimiter=",")
            temp_count += 1


class Net2Net:

    @staticmethod
    def net2wider(graphinfo,layer_index, units):
        """
        updated weight matrices are stored as csv files in the same tmp folder.
        So old weights are deleted. To save a trained model weights use the write_weights method in BuildModel class
        :param graphinfo: self-explanatory
        :param layer_index: index of layer(starting at 0) where the units are added.
        :param units: no. of units to be added.
        :return: a new GraphInfo obj with added units
        """
        try:
            assert units > 0
        except AssertionError as err:
            err.args = err.args + ("Cannot shrink, enter a positive number for units",)
            raise
        else:
            temp_obj = deepcopy(graphinfo)
            temp_obj.add_units(layer_index,units,inplace = True)
            prev_layers = graphinfo.layers
            # fetch the weight matrices in all layers
            weights = []
            for layer in range(prev_layers - 1):
                temp_fname = "temp/"+"w"+str(layer)+".csv"
                weights.append(np.genfromtxt(temp_fname,delimiter=","))

            """when new units are added in layer<layer_index>, weight matrices of layer<layer_index-1> and 
            layer<layer_index> will be updated.
            *   new weight matrix of layer<layer_index-1> will have new columns and existing columns are left undisturbed.
            *   New weight matrix of layer<layer_index> will have additional rows and existing row will be changed accordingly."""

            # updating weight matrix of layer<layer_index-1>
            # generate <units> random indices.
            total_cols = weights[layer_index - 1].shape[1]
            rand_col_idx = np.random.choice(total_cols,size = units, replace = True)

            rand_cols = weights[layer_index-1][:,rand_col_idx]

            # append these randomly selected weights to the existing matrix
            weights[layer_index-1] = np.append(weights[layer_index-1],rand_cols,axis = 1)

            # updating the weights in layer<layer_index>
            # this new weight matrix will have new row and existing rows will be updated
            count_dict = dict()
            for idx in rand_col_idx:
                if idx in count_dict:
                    count_dict[idx] += 1
                else:
                    count_dict[idx] = 2
            for idx, count in count_dict.items():
                weights[layer_index][idx,:] = weights[layer_index][idx,:]/float(count)

            # build new weight matrix
            for idx in rand_col_idx:
                new_row = weights[layer_index][idx,:]
                weights[layer_index] = np.vstack((weights[layer_index],new_row))

            write_temp(weights)
            return temp_obj

    @staticmethod
    def net2deeper(graphinfo, layer_index):
        """
        Assumes, no. of units in the new layer is same as the previous layer
        :param graphinfo: as the name implies
        :param layer_index: index of layer after which the new layer is created
        :return weight matrices of all layers including the newly created one.
        """
        temp_obj = deepcopy(graphinfo)
        temp_obj.insert_layer(layer_index,inplace=True)

        prev_layers = graphinfo.layers
        prev_units = graphinfo.units

        # fetch the weight matrices in all layers
        weights = []
        for layer in range(prev_layers - 1):
            temp_fname = "temp/" + "w" + str(layer) + ".csv"
            weights.append(np.genfromtxt(temp_fname, delimiter=","))

        # create identity matrix
        dims = prev_units[layer_index]
        id_matrix = np.identity(dims)

        weights.insert(layer_index,id_matrix)
        write_temp(weights)

        return temp_obj


if __name__ == "__main__":
    print("Use the main.py to test the model and for example")
    obj1 = GraphInfo(id = 1, layers = 3, ls_units=[784,30,10])
    model1 = BuildModel(obj1)
    model1.train(20)
    model1.write_weights()