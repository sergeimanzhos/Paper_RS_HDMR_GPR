import numpy as np
import matplotlib.pyplot as plt
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
import pandas as pd
from sklearn.model_selection import train_test_split
import itertools


#### define a function that computes rmse
def rmse(ypred, ytest):
    Sqerr = np.power(ytest - ypred, 2)
    MSE = np.sum(Sqerr)
    rmse = np.sqrt(MSE / ytest.size)
    return rmse



def sumcol(F, j):
    """"
    define a function to sum the  columns of a data except column with index i
    """
    s = np.zeros(F.shape[0])
    for i in range(F.shape[1]):
        if i == j:
            i += 1
        else:
            s = s + F[:, i]
    return s


def RS_HDMR_GPR(X_train, y_train, X_test, y_test, order = 3, alpha = 1e-8, use_decay_alpha = 'no', scale_factor = 1, length_scale = 0.6,
            number_cycles = 10, init = 'naive', plot_error_bars = 'no', mixe = 'no', optimizer = None):
    """
    This function fits  a RS-HDMR-GPR to data using independent Gaussian Processes for component functions. GPR is used from the python package GaussianProcessRegressor from sklearn.
    :parameters of the function are:
    :param X_train: DataFrame
        the training input data as returned from train_test_split function.
    :param y_train: DataFrame
        the training output data as returned from train_test_split function.
    :param X_test: DataFrame
        the test input data as returned from train_test_split function.
    :param y_test: DataFrame
        the test output data as returned from train_test_split function.
    :param order: int
        the order of the HDMR to use.
    :param alpha: float
        Value added to the diagonal of the kernel matrix during fitting.  Note that this is equivalent to adding a WhiteKernel with c=alpha.
    :param use_decay_alpha: string
        if 'yes' then decay alpha from cycle to cycle (default is "no")
    :param scale_factor: float
        the scale factor, equal to: y.max() - y.min()
    :param length_scale: float
        length scale of the Gaussian kernel
    :param number_cycles: int
        number of cycles to run the model
    :param init: str
        initialization of component functions ("naive" or "poly" using polynomial interpolations in 1D spaces): default is naive
    :param plot_error_bars: string
        if the user want to plot or not the error bars (default is "no")
    :param mixe: string
        in the user want to mix after fitting one component function (default is "no")
    :param optimizer: string
        if the user want to use optimizer then should name the optimizer (default is None)
    """
    all_combos = np.array(list(itertools.combinations(X_train, order))) # return all combinations of component functions
    mean = y_train.mean()
    if init == 'naive':
        component_function_train = (1 / all_combos.shape[0]) * mean * np.ones((X_train.shape[0], all_combos.shape[0]))  # initialize the matrix for the of component functions to zeros, shape is n*D
    if init == 'poly':
        component_function_train = np.ones((X_train.shape[0], all_combos.shape[
            0]))  # initialize the matrix for the of component functions to zeros, shape is n*D
        for i in range(0, all_combos.shape[0]):
            x = pd.DataFrame(X_train)[all_combos[i][0]]
            print(x.ndim)
            f = np.polyfit(x, y_train, 3)
            f = np.poly1d(f)
            component_function_train[:, i] = f(x)  # use interpolation function returned by `interp1d`
        print('Polynomial initialization used to initialize component functions')

    # Kernel bloc
    l = length_scale
    rbf = RBF(length_scale=l, length_scale_bounds=(1e-2, 1e2))  # + WhiteKernel(noise_level=1e-05)
    GPR = [GaussianProcessRegressor(kernel=rbf, alpha=alpha, optimizer=optimizer) for i in
           range(0, all_combos.shape[0])]

    # Train bloc
    for k in range(number_cycles):
        print('cycle number', k + 1)
        if use_decay_alpha == 'yes':
            if k < 2:
                GPR = [GaussianProcessRegressor(kernel=rbf, alpha=alpha, optimizer=optimizer) for i in
                       range(0, all_combos.shape[0])]
            elif k >= 2 and k < 8:
                GPR = [GaussianProcessRegressor(kernel=rbf, alpha=alpha * 1e-1, optimizer=optimizer) for i in
                       range(0, all_combos.shape[0])]
                alpha = alpha * 1e-1
                print('noise=', alpha)
            else:
                GPR = [GaussianProcessRegressor(kernel=rbf, alpha=alpha, optimizer=optimizer) for i in
                       range(0, all_combos.shape[0])]

        for i in range(0, all_combos.shape[0]):  # loop for in range the number of component functions
            vect = y_train - sumcol(component_function_train, i)
            component_function_train[:,i] = vect  # step1: output - inititializations
            xx = pd.DataFrame(X_train)[all_combos[i]]  # just reshape the input to be adequate with the model
            GPR[i].fit(xx, component_function_train[:, i])  # fit
            if mixe == 'yes':
                component_function_train[:, i] = (GPR[i].predict(xx) + vect) / 2
            else:
                component_function_train[:, i] = GPR[i].predict(xx)  # predict to re use component_function_train
        rmse_train = rmse(y_train * scale_factor, sumcol(component_function_train, 10000)*scale_factor)
        print('train rmse', rmse_train)  # compute rmse (it is computed on y_train)

    # Test bloc
    component_function_test = np.zeros((X_test.shape[0], all_combos.shape[0]))
    errorbars = np.zeros((X_test.shape[0], all_combos.shape[0]))
    for i in range(0, all_combos.shape[0]):  # loop for in range the number of component functions
        xt = pd.DataFrame(X_test)[all_combos[i]]  # just reshapint the input to be adequate with the model
        component_function_test[:, i], errorbars[:, i] = GPR[i].predict(xt, return_std=True)  # predict to re use component_function_test
        errorbars[:, i]=errorbars[:, i] * errorbars[:, i]
    ypred = sumcol(component_function_test, 10000)
    y_pred_scaled = ypred * scale_factor
    error_bars= np.sqrt(sumcol(errorbars, 5000))
    rmse_test = rmse(y_test * scale_factor, ypred * scale_factor)
    print('test rmse', rmse_test)

    print('order of the HDMR is', order)

    # Figures bloc
    fig, ax1 = plt.subplots()
    ax1.plot(y_test * scale_factor, y_pred_scaled, 'bo', markersize=1)
    ax1.set_xlabel('Target', fontsize=14)
    ax1.set_ylabel('Predictions', fontsize=14)
    ax1.grid(True)
    plt.show(block=True)
    if plot_error_bars == 'yes':
        fig, ax3 = plt.subplots()
        plt.errorbar(y_test * scale_factor, ypred * scale_factor, yerr = error_bars * scale_factor, ecolor = 'red', fmt = 'bo', markersize = 1)
        ax3.set_xlabel('Target', fontsize=14)
        ax3.set_ylabel('Predictions', fontsize=14)
        ax3.grid(True)
        plt.show(block=True)

    return rmse_train, rmse_test, sumcol(component_function_test, 50000), GPR, y_pred_scaled, error_bars * scale_factor

if __name__ == '__main__':
    # 6D Dataset read
    df =pd.read_table('E:/Graduation internship/datas/bondSobol120000pts.dat',header=None,delimiter=r"\s+")
    x = df.iloc[:, 0:6]
    y = df.iloc[:, -1]
    scale_factor = y.max()-y.min()
    X = (x-x.min())/(x.max()-x.min())
    y = (y-y.min())/(y.max()-y.min())

    #Split the data into train and test
    X_train, X_test, y_train, y_test= train_test_split(X, y,train_size=0.03, test_size=0.1,random_state=42)

    HDMR = RS_HDMR_GPR(X_train, y_train, X_test, y_test, order = 3, alpha = 1e-5, use_decay_alpha = 'yes', scale_factor = scale_factor, length_scale=0.6, number_cycles = 5, init = 'poly', plot_error_bars = 'yes', mixe = 'no', optimizer = None)
