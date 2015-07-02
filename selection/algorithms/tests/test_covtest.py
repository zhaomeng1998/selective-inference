import numpy as np
import itertools
import numpy.testing.decorators as dec
from matplotlib import pyplot as plt

from selection.algorithms.lasso import instance, lasso
from selection.algorithms.covtest import covtest, selected_covtest
from selection.constraints.affine import gibbs_test

def test_covtest():

    n, p = 30, 50
    X = np.random.standard_normal((n,p)) + np.random.standard_normal(n)[:,None]
    X /= X.std(0)[None,:]
    Y = np.random.standard_normal(n) * 1.5 

    for exact, covariance in itertools.product([True, False],
                                               [None, np.identity(n)]):
        con, pval, idx, sign = covtest(X, Y, sigma=1.5, exact=exact,
                                       covariance=covariance)
    for covariance in [None, np.identity(n)]:
        con, pval, idx, sign = selected_covtest(X, Y, sigma=1.5,
                                                covariance=covariance)

    con, pval, idx, sign = selected_covtest(X, Y)

    return pval

@dec.slow
def test_tilting(nsim=100):

    P = []
    covered0 = 0
    coveredA = 0
    screen = 0

    for i in range(nsim):
        X, Y, beta, active, sigma = instance(n=20, p=30)

        Y0 = np.random.standard_normal(X.shape[0]) * sigma

        # null pvalues and intervals

        cone, pvalue, idx, sign = selected_covtest(X, Y0, sigma=sigma)
        eta = X[:,idx] * sign
        p1, _, _, fam = gibbs_test(cone, Y0, eta, 
                                   ndraw=50000,
                                   burnin=10000,
                                   alternative='twosided',
                                   sigma_known=True,
                                   tilt=eta,
                                   UMPU=False)

        observed_value = (Y0 * eta).sum()
        lower_lim, upper_lim = fam.equal_tailed_interval(observed_value)
        lower_lim_final = np.dot(eta, np.dot(cone.covariance, eta)) * lower_lim
        upper_lim_final = np.dot(eta, np.dot(cone.covariance, eta)) * upper_lim
        covered0 += (lower_lim_final < 0) * (upper_lim_final > 0)
        print covered0 / (i + 1.), 'coverage0'

        # compare to no tilting

        p2 = gibbs_test(cone, Y0, X[:,idx] * sign,
                        ndraw=50000,
                        burnin=10000,
                        alternative='twosided',
                        sigma_known=True,
                        tilt=None,
                        UMPU=False)[0]
        print p2, 'huh'
        P.append((p1, p2))
        Pa = np.array(P)

        # p1 and p2 should be very close, so have high correlation
        print np.corrcoef(Pa.T)[0,1], 'correlation'

        # they should also look uniform -- mean should be about 0.5, sd about 0.29

        print np.mean(Pa, 0), 'mean of nulls'
        print np.std(Pa, 0), 'sd of nulls'

        # alternative intervals

        mu = 3 * X[:,0] * sigma
        YA = np.random.standard_normal(X.shape[0]) * sigma + mu 

        cone, pvalue, idx, sign = selected_covtest(X, YA, sigma=sigma)
        _, _, _, fam = gibbs_test(cone, YA, X[:,idx] * sign,
                                  ndraw=15000,
                                  burnin=10000,
                                  alternative='greater',
                                  sigma_known=True,
                                  tilt=eta)

        if idx == 0:
            screen += 1

            eta = X[:,0] * sign
            observed_value = (YA * eta).sum()
            target = (eta * mu).sum()
            lower_lim, upper_lim = fam.equal_tailed_interval(observed_value)
            lower_lim_final = np.dot(eta, np.dot(cone.covariance, eta)) * lower_lim
            upper_lim_final = np.dot(eta, np.dot(cone.covariance, eta)) * upper_lim
            print lower_lim_final, upper_lim_final, target
            coveredA += (lower_lim_final < target) * (upper_lim_final > target)
            print coveredA / (screen * 1.), 'coverageA'

        print screen / (i + 1.), 'screening'

    plt.figure()
    plt.scatter(Pa[:,0], Pa[:,1])

    try:
        import statsmodels.api as sm
        plt.figure()
        G = np.linspace(0, 1, 101)
        plt.plot(G, sm.distributions.ECDF(Pa[:,0])(G))
        plt.plot(G, sm.distributions.ECDF(Pa[:,1])(G))
    except ImportError: # no statsmodels
        pass
