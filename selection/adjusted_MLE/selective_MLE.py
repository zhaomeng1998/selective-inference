import numpy as np
import regreg.api as rr
from selection.randomized.M_estimator import M_estimator

class M_estimator_map(M_estimator):

    def __init__(self, loss, epsilon, penalty, randomization, randomization_scale = 1.):
        M_estimator.__init__(self, loss, epsilon, penalty, randomization)
        self.randomizer = randomization
        self.randomization_scale = randomization_scale

    def solve_approx(self):
        self.solve()
        (_opt_linear_term, _opt_affine_term) = self.opt_transform
        self._opt_linear_term = np.concatenate(
            (_opt_linear_term[self._overall, :], _opt_linear_term[~self._overall, :]), 0)
        self._opt_affine_term = np.concatenate((_opt_affine_term[self._overall], _opt_affine_term[~self._overall]), 0)
        self.opt_transform = (self._opt_linear_term, self._opt_affine_term)

        (_score_linear_term, _) = self.score_transform
        self._score_linear_term = np.concatenate(
            (_score_linear_term[self._overall, :], _score_linear_term[~self._overall, :]), 0)
        self.score_transform = (self._score_linear_term, np.zeros(self._score_linear_term.shape[0]))
        self.feasible_point = np.abs(self.initial_soln[self._overall])
        nactive = self._overall.sum()
        self.inactive_subgrad = self.observed_opt_state[nactive:]


        lagrange = []
        for key, value in self.penalty.weights.iteritems():
            lagrange.append(value)
        lagrange = np.asarray(lagrange)
        self.inactive_lagrange = lagrange[~self._overall]

        X, _ = self.loss.data
        n, p = X.shape
        self.p = p


        score_cov = np.zeros((p, p))
        X_active_inv = np.linalg.inv(X[:,self._overall].T.dot(X[:,self._overall]))
        projection_perp = np.identity(n) - X[:,self._overall].dot(X_active_inv).dot( X[:,self._overall].T)
        score_cov[:nactive, :nactive] = X_active_inv
        score_cov[nactive:, nactive:] = X[:,~self._overall].T.dot(projection_perp).dot(X[:,~self._overall])

        self.score_target_cov = score_cov[:, :nactive]
        self.target_cov = score_cov[:nactive, :nactive]
        self.target_observed = self.observed_internal_state[:nactive]
        self.observed_score_state = self.observed_internal_state
        self.nactive = nactive

        self.B_active = self._opt_linear_term[:nactive, :nactive]
        self.B_inactive = self._opt_linear_term[nactive:, :nactive]
        self.B = np.vstack([self.B_active, self.B_inactive])


    def setup_map(self, j):

        self.A = np.dot(self._score_linear_term, self.score_target_cov[:, j]) / self.target_cov[j, j]
        self.null_statistic = self._score_linear_term.dot(self.observed_score_state) - self.A * self.target_observed[j]

        self.offset_active = self._opt_affine_term[:self.nactive] + self.null_statistic[:self.nactive]
        self.offset_inactive = self.null_statistic[self.nactive:]

def solve_UMVU(target_transform,
               opt_transform,
               target_observed,
               feasible_point,
               target_cov,
               randomizer_precision,
               step=1,
               nstep=30,
               tol=1.e-8):

    A, data_offset = target_transform # data_offset = N
    B, opt_offset = opt_transform     # opt_offset = u

    nfeature, nopt = B.shape[1]
    ntarget = A.shape[1]

    # XXX should be able to do vector version as well
    # but for now code assumes 1dim
    assert ntarget == 1

    # setup joint implied covariance matrix

    inverse_target_cov = np.linalg.inv(target_cov)
    inverse_cov = np.zeros((ntarget + nopt, ntarget + nopt))
    inverse_cov[:ntarget,:ntarget] = A.T.dot(randomizer_precision).dot(A) + inverse_target_cov
    inverse_cov[:ntarget,ntarget:] = A.T.dot(randomizer_precision).dot(B)
    inverse_cov[ntarget:,:ntarget] = B.T.dot(randomizer_precision).dot(A)
    inverse_cov[nopt:,nopt:] = B.T.dot(randomizer_precision).dot(B)
    cov = np.linalg.inv(inverse_cov)

    cov_opt = cov[ntarget:,ntarget:]
    implied_cov_target = cov[:ntarget,:ntarget]
    cross_cov = cov[:ntarget,ntarget:]

    L = cross_cov.dot(np.linalg.inv(cov_opt))
    M_1 = np.linalg.inv(inverse_cov[:ntarget,:ntarget]).dot(inverse_target_cov)
    M_2 = np.linalg.inv(inverse_cov[:ntarget,:ntarget]).dot(A.T.dot(randomizer_precision))

    conditioned_value = data_offset + opt_offset
    conditional_par = (inverse_cov[ntarget:,ntarget:].dot(cross_cov.T.dot(np.linalg.inv(implied_cov_target).dot(target_observed))) + \
                           B.T.dot(randomizer_precision).dot(conditioned_value))
    conditional_var_inv = inverse_cov[ntarget:,ntarget:]

    objective = lambda u: u.T.dot(conditional_par) - u.T.dot(conditional_var_inv).dot(u)/2. - np.log(1.+ 1./u).sum()
    grad = lambda u: conditional_par - conditional_var_inv.dot(u) - 1./(1.+ u) + 1./u

    current = feasible_point
    current_value = np.inf

    for itercount in range(nstep):
        newton_step = grad(current)

        # make sure proposal is feasible

        count = 0
        while True:
            count += 1
            proposal = current - step * newton_step
            if np.all(proposal > 0):
                break
            step *= 0.5
            if count >= 40:
                raise ValueError('not finding a feasible point')

        # make sure proposal is a descent

        count = 0
        while True:
            proposal = current - step * newton_step
            proposed_value = objective(proposal)
            if proposed_value <= current_value:
                break
            step *= 0.5

        # stop if relative decrease is small

        if np.fabs(current_value - proposed_value) < tol * np.fabs(current_value):
            current = proposal
            current_value = proposed_value
            break

        current = proposal
        current_value = proposed_value

        if itercount % 4 == 0:
            step *= 2

    value = objective(current)
    return -np.linalg.inv(M_1).dot(L.dot(current))+ np.linalg.inv(M_1).dot(target_observed- M_2.dot(conditioned_value)), value























